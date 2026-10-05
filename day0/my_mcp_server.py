# file: my_mcp_server.py
from fastmcp import FastMCP

# Create the server with a name and description
mcp = FastMCP("HR Tools Server")

# Define tools using @mcp.tool() — similar to @tool from LangChain
@mcp.tool()
def get_employee(employee_id: str) -> dict:
    """Look up an employee by their ID.

    Args:
        employee_id: The employee's unique ID. Example: 'EMP-001'.

    Returns:
        Employee record with name, department, manager, and leave balance.
    """
    employees = {
        "EMP-001": {
            "name": "Priya Sharma",
            "department": "Engineering",
            "manager": "Raj Kumar",
            "annual_leave_remaining": 12
        },
        "EMP-002": {
            "name": "David Chen",
            "department": "Finance",
            "manager": "Sarah Lee",
            "annual_leave_remaining": 8
        },
    }
    employee = employees.get(employee_id)
    if not employee:
        return {"error": f"No employee found with ID '{employee_id}'"}
    return employee

@mcp.tool()
def check_leave_balance(employee_id: str, leave_type: str = "annual") -> dict:
    """Check the leave balance for an employee.

    Args:
        employee_id: The employee's unique ID.
        leave_type: Type of leave to check. Options: 'annual', 'sick', 'personal'.

    Returns:
        Leave balance details including days remaining and days used.
    """
    balances = {
        "EMP-001": {"annual": 12, "sick": 7, "personal": 2},
        "EMP-002": {"annual": 8,  "sick": 10, "personal": 3},
    }
    emp_balance = balances.get(employee_id)
    if not emp_balance:
        return {"error": f"Employee '{employee_id}' not found"}

    days_remaining = emp_balance.get(leave_type, 0)
    return {
        "employee_id": employee_id,
        "leave_type": leave_type,
        "days_remaining": days_remaining,
        "total_days": 20 if leave_type == "annual" else 10
    }

@mcp.tool()
def request_leave(
    employee_id: str,
    leave_type: str,
    days: int,
    reason: str
) -> dict:
    """Submit a leave request for an employee.

    Args:
        employee_id: The employee's unique ID.
        leave_type: Type of leave: 'annual', 'sick', or 'personal'.
        days: Number of days requested. Must be positive.
        reason: Brief reason for the leave request.

    Returns:
        Request confirmation with a request ID and approval status.
    """
    import uuid
    if days <= 0:
        return {"error": "Days must be a positive number"}

    request_id = f"LR-{uuid.uuid4().hex[:6].upper()}"
    # Requests of 2 days or less are auto-approved
    status = "approved" if days <= 2 else "pending_manager_approval"

    return {
        "request_id": request_id,
        "employee_id": employee_id,
        "leave_type": leave_type,
        "days_requested": days,
        "status": status,
        "message": f"Request {request_id} submitted. Status: {status}"
    }

# --- Run the server ---
if __name__ == "__main__":
    print("Starting HR Tools MCP Server on http://localhost:8001/mcp")
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8001, path="/mcp")