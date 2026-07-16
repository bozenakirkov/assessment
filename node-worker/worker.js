const axios = require("axios");


const API_URL = "http://app:5000";


async function getPendingActions() {

    const response = await axios.get(
        `${API_URL}/actions/pending`
    );

    return response.data;
}


async function processAction(action) {

    console.log(
        "Processing:",
        action.id,
        action.type
    );


    if (action.type === "VALIDATE") {

        const payload = action.payload;

        if (payload.amount > 0) {

            return {
                status: "SUCCESS",
                result: {
                    validated: true
                }
            };

        } else {

            return {
                status: "FAILED",
                error: "Amount must be positive"
            };
        }
    }


    if (action.type === "PROCESS") {

        const delay =
            Math.floor(
                Math.random() * 1000
            ) + 500;


        await sleep(delay);


        const failed =
            Math.random() < 0.2;


        if (failed) {

            return {
                status:"FAILED",
                error:"External processing failed"
            };

        }


        return {
            status:"SUCCESS",
            result:{
                processed:true
            }
        };
    }


    return {
        status:"FAILED",
        error:"Unknown action type"
    };
}



async function sendResult(action, result) {

    await axios.post(
        `${API_URL}/actions/${action.id}/result`,
        result
    );

    console.log(
        "Result sent:",
        action.id,
        result.status
    );
}



function sleep(ms) {

    return new Promise(
        resolve => setTimeout(resolve, ms)
    );
}



async function workerLoop(){

    console.log(
        "Worker started"
    );


    while(true){

        try {

            const actions =
                await getPendingActions();


            for(const action of actions){

                const result =
                    await processAction(action);


                await sendResult(
                    action,
                    result
                );
            }


        }
        catch(error){

            console.error(
                error.message
            );

        }


        await sleep(3000);
    }
}



workerLoop();