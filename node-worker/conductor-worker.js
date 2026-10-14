const axios = require("axios");

const CONDUCTOR_API_URL =
  process.env.CONDUCTOR_API_URL || "http://host.docker.internal:8127/api";

const TASK_NAME = "validate_payload";
const WORKER_ID = process.env.WORKER_ID || "validate-payload-worker";
const POLL_INTERVAL_MS = 2000;

async function pollTask() {
  try {
    const response = await axios.get(
      `${CONDUCTOR_API_URL}/tasks/poll/${TASK_NAME}`,
      { timeout: 10000 }
    );

    const task = response.data;

    if (!task || !task.taskId) {
      return;
    }

    console.log("task_received", {
      taskId: task.taskId,
      reference: task.inputData?.reference,
    });

    await handleTask(task);
  } catch (error) {
    console.error("poll_failed", error.message);
  }
}

async function handleTask(task) {
  const reference = task.inputData?.reference;
  const payload = task.inputData?.payload || {};
  const amount = payload.amount;

  if (typeof amount !== "number") {
    await failTask(task, "payload.amount must be a number");
    return;
  }

  if (amount <= 0) {
    await failTask(task, "amount must be greater than 0");
    return;
  }

  await completeTask(task, {
    validated: true,
    reference,
    amount,
  });
}

async function completeTask(task, outputData) {
  try {
    await axios.post(
      `${CONDUCTOR_API_URL}/tasks`,
      {
        taskId: task.taskId,
        workflowInstanceId: task.workflowInstanceId,
        workerId: WORKER_ID,
        status: "COMPLETED",
        outputData,
      },
      { timeout: 10000 }
    );

    console.log("task_completed", {
      taskId: task.taskId,
      reference: task.inputData?.reference,
    });
  } catch (error) {
    console.error("complete_failed", error.message);
  }
}

async function failTask(task, reason) {
  try {
    await axios.post(
      `${CONDUCTOR_API_URL}/tasks`,
      {
        taskId: task.taskId,
        workflowInstanceId: task.workflowInstanceId,
        workerId: WORKER_ID,
        status: "FAILED",
        reasonForIncompletion: reason,
      },
      { timeout: 10000 }
    );

    console.error("task_failed", {
      taskId: task.taskId,
      reference: task.inputData?.reference,
      reason,
    });
  } catch (error) {
    console.error("fail_failed", error.message);
  }
}

async function main() {
  console.log("worker_started", {
    task: TASK_NAME,
    conductor: CONDUCTOR_API_URL,
  });

  while (true) {
    await pollTask();
    await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
  }
}

main().catch((error) => {
  console.error("worker_crashed", error);
  process.exit(1);
});