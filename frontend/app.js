const API_URL = "http://localhost:5000";


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

            div.innerHTML = `
                <h3>
                    ${workflow.reference}
                </h3>

                <p>
                    State:
                    <strong>${workflow.state}</strong>
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
                    onclick="startValidation(${workflow.id})">
                    START_VALIDATION
                </button>


                <button 
                    onclick="startProcessing(${workflow.id})">
                    START_PROCESSING
                </button>


                <button 
                    onclick="cancelWorkflow(${workflow.id})">
                    CANCEL
                </button>


                <button 
                    onclick="showHistory(${workflow.id})">
                    HISTORY
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
async function showHistory(id) {

    try {

        const response = await fetch(
            `${API_URL}/workflows/${id}/history`
        );


        const history = await response.json();


        console.log(history);


        alert(
            JSON.stringify(
                history,
                null,
                2
            )
        );


    } catch(error) {

        alert(error.message);

    }

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