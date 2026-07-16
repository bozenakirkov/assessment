const API_URL = "http://localhost:5000";


function getAvailableActions(state) {

    return {
        canStartValidation: state === "CREATED",

        canStartProcessing: state === "APPROVED",

        canCancel: [
            "CREATED",
            "VALIDATING",
            "APPROVED"
        ].includes(state)
    };

}

function getStateClass(state) {

    switch (state) {

        case "CREATED":
            return "created";

        case "VALIDATING":
            return "validating";

        case "APPROVED":
            return "approved";

        case "PROCESSING":
            return "processing";

        case "COMPLETED":
            return "completed";

        case "VALIDATION_FAILED":
            return "validation-failed";

        case "PROCESSING_FAILED":
            return "processing-failed";

        case "CANCELLED":
            return "cancelled";

        default:
            return "";
    }

}


// Load workflows from Flask API
async function loadWorkflows() {

    try {
        const response = await fetch(`${API_URL}/workflows`);

        if (!response.ok) {
            throw new Error("Failed to load workflows");
        }

        const workflows = await response.json();

        const container = document.getElementById("workflows");

        container.innerHTML = "";


        workflows.forEach(workflow => {

            const div = document.createElement("div");
            div.className = "workflow";

            const actions = getAvailableActions(workflow.state);

            const stateClass = getStateClass(workflow.state);

            div.innerHTML = `
                <h3>
                    ${workflow.reference}
                </h3>

                <p>
                    <span class="state-badge ${stateClass}">
                        ${workflow.state}
                    </span>
                </p>

                <p>
                    Version:
                    ${workflow.version}
                </p>

                <p>
                    Updated:
                    ${workflow.updatedAt}
                </p>


                <button
                    onclick="startValidation(${workflow.id})"
                    ${actions.canStartValidation ? "" : "disabled"}>
                    START_VALIDATION
                </button>


                <button
                    onclick="startProcessing(${workflow.id})"
                    ${actions.canStartProcessing ? "" : "disabled"}>
                    START_PROCESSING
                </button>


                <button
                    onclick="cancelWorkflow(${workflow.id})"
                    ${actions.canCancel ? "" : "disabled"}>
                    CANCEL
                </button>


                <button 
                    onclick="showDetails(${workflow.id})">
                    DETAILS
                </button>


                <hr>
            `;


            container.appendChild(div);

        });


    } catch(error) {

        console.error(error);

        document.getElementById("workflows").innerHTML =
            `
            <p style="color:red">
                ${error.message}
            </p>
            `;
    }
}



// START_VALIDATION transition
async function startValidation(id) {

    await sendTransition(id, "START_VALIDATION");

}



// START_PROCESSING transition
async function startProcessing(id) {

    await sendTransition(id, "START_PROCESSING");

}



// CANCEL transition
async function cancelWorkflow(id) {

    await sendTransition(id, "CANCEL");

}



// Common transition function
async function sendTransition(id, action) {

    try {

        const response = await fetch(
            `${API_URL}/workflows/${id}/transitions`,
            {
                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify({
                    action: action
                })
            }
        );


        const result = await response.json();


        if (!response.ok) {

            alert(
                result.message || "Transition failed"
            );

            return;
        }


        console.log(result);


        // reload UI
        loadWorkflows();


    } catch(error) {

        alert(error.message);

    }

}


// Show workflow history
async function showDetails(id) {

    const workflowResponse =
        await fetch(`${API_URL}/workflows/${id}`);

    const historyResponse =
        await fetch(`${API_URL}/workflows/${id}/history`);

    const actionsResponse =
        await fetch(`${API_URL}/workflows/${id}/actions`);


    const workflow = await workflowResponse.json();
    const history = await historyResponse.json();
    const actions = await actionsResponse.json();


    document.getElementById("details").innerHTML = `
        <h3>Payload</h3>

            <table class="data-table">
                <thead>
                    <tr>
                        <th>Key</th>
                        <th>Value</th>
                    </tr>
                </thead>
            
                <tbody>
                    ${Object.entries(workflow.payload).map(([key, value]) => `
                        <tr>
                            <td>${key}</td>
                            <td>${value}</td>
                        </tr>
                    `).join("")}
                </tbody>
            </table>

        <h3>Actions</h3>
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Action</th>
                        <th>Status</th>
                        <th>Attempt</th>
                        <th>Created</th>
                        <th>Updated</th>
                    </tr>
                </thead>
                <tbody>
                    ${actions.map(a => `
                        <tr>
                            <td>${a.type}</td>
                            <td>${a.status}</td>
                            <td>${a.attempt}</td>
                            <td>${a.createdAt}</td>
                            <td>${a.updatedAt}</td>
                        </tr>
                    `).join("")}
                </tbody>
            </table>

        <h3>History</h3>
            <table class="data-table">
                <thead>
                    <tr>
                        <th>From</th>
                        <th>Action</th>
                        <th>To</th>
                        <th>Timestamp</th>
                    </tr>
                </thead>
            
                <tbody>
                    ${history.map(h => `
                        <tr>
                            <td>${h.fromState}</td>
                            <td>${h.action}</td>
                            <td>${h.toState}</td>
                            <td>${h.timestamp}</td>
                        </tr>
                    `).join("")}
                </tbody>
            </table>
            `;
}



// Create workflow
async function createWorkflow() {

    const reference =
        document.getElementById("reference").value;

    const amount =
        document.getElementById("amount").value;


    if (!reference) {
        alert("Reference is required");
        return;
    }


    try {

        const response = await fetch(
            `${API_URL}/workflows`,
            {
                method: "POST",

                headers:{
                    "Content-Type":"application/json"
                },

                body: JSON.stringify({

                    reference: reference,

                    payload:{
                        customerId: "customer-1",
                        amount: Number(amount)
                    }

                })
            }
        );


        const result = await response.json();


        if (!response.ok) {

            alert(result.message);

            return;
        }


        console.log(result);

        // clear inputs
        document.getElementById("reference").value = "";
        document.getElementById("amount").value = "";


        loadWorkflows();


    } catch(error) {

        alert(error.message);

    }
}


// Initial load
loadWorkflows();


// Auto refresh every 5 seconds
setInterval(
    loadWorkflows,
    5000
);