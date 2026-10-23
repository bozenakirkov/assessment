const axios = require("axios");

const CONDUCTOR_API_URL = (
  process.env.CONDUCTOR_API_URL || "http://conductor:8080/api"
).replace(/\/+$/, "");

const TASK_NAMES = ["validate_payload", "process_payload"];
const WORKER_ID = process.env.WORKER_ID || "payload-worker";
const POLL_INTERVAL_MS = 2000;
const REQUEST_TIMEOUT_MS = 10000;

const APP_API_URL = (process.env.API_URL || "http://app:5000").replace(/\/+$/, "");

async function reportToApp(task, result) {
  const actionId = task.inputData?.actionId;
  if (!actionId) {
    throw new Error("actionId missing from task input");
  }
  const body = result.status === "COMPLETED"
    ? { status: "SUCCESS", result: result.outputData }
    : { status: "FAILED", error: result.reasonForIncompletion };
  await axios.post(`${APP_API_URL}/actions/${actionId}/result`, body, { timeout: REQUEST_TIMEOUT_MS });
}

async function reportToAppWithRetry(task, result, attempts = 3) {
  for (let i = 1; i <= attempts; i++) {
    try {
      return await reportToApp(task, result);
    } catch (error) {
      // Missing actionId will never succeed, don't retry
      if (i === attempts || !task.inputData?.actionId) throw error;
      await sleep(2000 * i);
    }
  }
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function taskContext(task, taskName) {
  return {
    taskName,
    taskId: task.taskId,
    workflowId: task.workflowInstanceId,
    reference: task.inputData?.reference,
  };
}

function validatePayload(task) {
  const reference = task.inputData?.reference;
  const payload = task.inputData?.payload || {};
  const amount = payload.amount;

  if (typeof amount !== "number") {
    return {
      status: "FAILED",
      reasonForIncompletion: "payload.amount must be a number",
    };
  }

  if (amount <= 0) {
    return {
      status: "FAILED",
      reasonForIncompletion: "amount must be greater than 0",
    };
  }

  return {
    status: "COMPLETED",
    outputData: {
      validated: true,
      reference,
      amount,
    },
  };
}

async function processPayload() {
  const delay = Math.floor(Math.random() * 1000) + 500;
  await sleep(delay);

  if (Math.random() < 0.2) {
    return {
      status: "FAILED",
      reasonForIncompletion: "External processing failed",
    };
  }

  return {
    status: "COMPLETED",
    outputData: {
      processed: true,
    },
  };
}

async function executeTask(task, taskName) {
  switch (taskName) {
    case "validate_payload":
      return validatePayload(task);

    case "process_payload":
      return processPayload();

    default:
      throw new Error(`Unsupported task type: ${taskName}`);
  }
}

async function handleTask(task, taskName) {
  const context = taskContext(task, taskName);
  let result;

  try {
    result = await executeTask(task, taskName);
  } catch (error) {
    console.error("task_execution_failed", {
      ...context,
      error: error.message,
    });

    result = {
      status: "FAILED",
      reasonForIncompletion: error.message,
    };
  }

  // Report to the app (updates the workflow state in the database)
  try {
    await reportToAppWithRetry(task, result);
    console.log("app_result_reported", { ...context, status: result.status });
  } catch (error) {
    console.error("app_result_report_failed", {
      ...context,
      intendedStatus: result.status,
      error: error.message,
      httpStatus: error.response?.status,
      response: error.response?.data,
    });

    // The database was not updated, so the Conductor task must not show COMPLETED
    result = {
      status: "FAILED",
      reasonForIncompletion: `App result report failed: ${error.message}`,
    };
  }

  // Keep result reporting separate from execution.
  try {
    await axios.post(
      `${CONDUCTOR_API_URL}/tasks`,
      {
        taskId: task.taskId,
        workflowInstanceId: task.workflowInstanceId,
        workerId: WORKER_ID,
        ...result,
      },
      { timeout: REQUEST_TIMEOUT_MS }
    );

    console.log("task_result_reported", {
      ...context,
      status: result.status,
      reason: result.reasonForIncompletion,
    });
  } catch (error) {
    console.error("task_result_report_failed", {
      ...context,
      intendedStatus: result.status,
      error: error.message,
      httpStatus: error.response?.status,
      response: error.response?.data,
    });
  }
}

async function pollTask(taskName) {
  let task;

  try {
    const response = await axios.get(
      `${CONDUCTOR_API_URL}/tasks/poll/${taskName}`,
      {
        params: { workerid: WORKER_ID },
        timeout: REQUEST_TIMEOUT_MS,
      }
    );

    task = response.data;
  } catch (error) {
    console.error("poll_failed", {
      taskName,
      error: error.message,
      httpStatus: error.response?.status,
      response: error.response?.data,
    });
    return;
  }

  if (!task || !task.taskId) {
    return;
  }

  console.log("task_received", taskContext(task, taskName));
  await handleTask(task, taskName);
}

async function workerLoop(taskName) {
  while (true) {
    await pollTask(taskName);
    await sleep(POLL_INTERVAL_MS);
  }
}

async function main() {
  console.log("worker_started", {
    tasks: TASK_NAMES,
    workerId: WORKER_ID,
    conductor: CONDUCTOR_API_URL,
  });

  await Promise.all(TASK_NAMES.map((taskName) => workerLoop(taskName)));
}

main().catch((error) => {
  console.error("worker_crashed", error);
  process.exit(1);
});
