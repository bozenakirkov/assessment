# assessment

1. run Docker Desktop

docker compose down -v

2. docker compose up --build

3. open frontend/index.html



docker exec -it workflow_postgres \
psql -U postgres -d workflow_db \
-c "SELECT * FROM workflows;"

OR

docker exec -it workflow_postgres psql -U postgres -d workflow_db

# create workflow:
curl.exe -X POST http://localhost:5000/workflows -H "Content-Type: application/json" -d "@workflow.json"

expected result:
{
  "createdAt": "Wed, 15 Jul 2026 09:16:59 GMT",
  "id": 1,
  "reference": "order-123",
  "state": "CREATED",
  "version": 1
}

# action
curl.exe -X POST http://localhost:5000/workflows/1/transitions -H "Content-Type: application/json" -d "@transition.json"
expected result:
{
  "message": "Transition completed successfully",
  "state": "VALIDATING",
  "workflowId": 1
}

# result
curl.exe -X POST http://localhost:5000/actions/1/result -H "Content-Type: application/json" -d "@result.json"

# failed
curl.exe -X POST http://localhost:5000/actions/1/result -H "Content-Type: application/json" -d "@validation_failed.json"

# success
curl.exe -X POST http://localhost:5000/actions/3/result -H "Content-Type: application/json" -d "@validation_success.json"

expected result:
{
  "message": "Action result processed successfully",
  "state": "APPROVED",
  "workflowId": 3
}

# processint_transition
curl.exe -X POST http://localhost:5000/workflows/1/transitions -H "Content-Type: application/json" -d "@processing_transition.json"

expected:
{
  "message": "Transition completed successfully",
  "state": "PROCESSING",
  "workflowId": 1
}

# process-succes
curl.exe -X POST http://localhost:5000/actions/2/result -H "Content-Type: application/json" -d "@process_success.json"

#####
PS C:\Users\Bozena\PycharmProjects\PythonProject\SoftwareOne> curl.exe -X POST http://localhost:5000/workflows -H "Content-Type: application/json" -d "@workflow.json"
{
  "createdAt": "Wed, 15 Jul 2026 10:50:03 GMT",
  "id": 1,
  "reference": "order-123",
  "state": "CREATED",
  "version": 1
}
PS C:\Users\Bozena\PycharmProjects\PythonProject\SoftwareOne> curl.exe -X POST http://localhost:5000/workflows/1/transitions -H "Content-Type: application/json" -d "@transition.json"
{
  "message": "Transition completed successfully",
  "state": "VALIDATING",
  "workflowId": 1
}
PS C:\Users\Bozena\PycharmProjects\PythonProject\SoftwareOne> curl.exe -X POST http://localhost:5000/actions/1/result -H "Content-Type: application/json" -d "@validation_success.json"
{
  "message": "Action result processed successfully",
  "state": "APPROVED",
  "workflowId": 1
}
PS C:\Users\Bozena\PycharmProjects\PythonProject\SoftwareOne> curl.exe -X POST http://localhost:5000/workflows/1/transitions -H "Content-Type: application/json" -d "@processing_transition.json"
{
  "message": "Transition completed successfully",
  "state": "PROCESSING",
  "workflowId": 1
}
PS C:\Users\Bozena\PycharmProjects\PythonProject\SoftwareOne> curl.exe -X POST http://localhost:5000/actions/2/result -H "Content-Type: application/json" -d "@process_success.json"
{
  "message": "Action result processed successfully",
  "state": "COMPLETED",
  "workflowId": 1
}



# #########################################
install node.js
