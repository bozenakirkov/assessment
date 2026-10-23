const axios = require("axios");

const CONDUCTOR_API_URL = (
  process.env.CONDUCTOR_API_URL || "http://host.docker.internal:8127/api"
).replace(/\/+$/, "");

const TASK_NAMES = ["validate_payload", "process_payload"];
const WORKER_ID = process.env.WORKER_ID || "payload-worker";
const POLL_INTERVAL_MS = 2000;
const REQUEST_TIMEOUT_MS = 10000;

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

  // Keep result reporting separate from execution.
  // A reporting error must not turn successful work into a FAILED result.
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
