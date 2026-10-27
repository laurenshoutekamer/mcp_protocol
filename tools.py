import subprocess
import time
from datetime import date, datetime

def run_today_tool(tool_args):
    requested_date_format = tool_args.get("format")

    if not isinstance(requested_date_format, str) or requested_date_format == "":
        return (False, "Please provide the format so the program knows how to display the date, e.g. %y-%m-%d")
    else:
        try:
            return (True, date.today().strftime(requested_date_format))
        except ValueError:
            return (False, " the program did not accept the strftime format provided on this machine")



def run_weekday_tool(tool_args):
    usr_date_input = tool_args.get("date")

    if type(usr_date_input) != str or usr_date_input == "":
        return (False, " You are required to provide a string date argument for the weekday tool to work")
    else:
        try:
            return (True, datetime.strptime(usr_date_input, "%Y-%m-%d").strftime("%A"))
        except ValueError:
            return (False, "ensure you provided a valid date in the yyyt-mm-dd format")



def run_timer_tool(tool_arg_obj, start_reply, send_update):

    # input check
    duration_alarm = tool_arg_obj.get("alarm")
    timer_error = ""

    if type(duration_alarm) not in (int, float):
        timer_error = " please provide the alarm argument for the timer tool as an int or float"

    elif not 0 <= duration_alarm <= 300:
        timer_error = "the alarm needs to be at least 0 seconds and at most 300"

    if timer_error != "":
        return (False, timer_error)

#timer setup
    start_reply()
    start_time = time.monotonic()
    next_update_after = 10

    while True:
        seconds_passed = time.monotonic() - start_time
        remaining_sleep = min(next_update_after, duration_alarm) - seconds_passed
        
        if remaining_sleep > 0:
            time.sleep(remaining_sleep)
        seconds_passed = time.monotonic() - start_time
        
        if seconds_passed >= duration_alarm:
            break
        
        if seconds_passed >= next_update_after:
            time_elapsed_since_start = int(seconds_passed)
            seconds_left = duration_alarm - time_elapsed_since_start
            send_update(time_elapsed_since_start, duration_alarm, seconds_left)
            next_update_after = next_update_after + 10
            
    return (True, "The alarm is going off, the time is done. ")


def run_calculator_tool(tool_args):
    user_expression = tool_args.get("expression")
    if type(user_expression) != str or user_expression == "":
        return (False, "You need to provide a string expression as argument for the calculator tool")
    try:
        bc_result = subprocess.run(
            ["bc"],
            input=user_expression + "\n",
            text=True,
            capture_output=True,
            timeout=5
        )
    except subprocess.TimeoutExpired:
        return (False, " The calculator did not finish in time and was stopped as a precaution")

    error_bc = bc_result.stderr.strip()
    if bc_result.returncode != 0 or error_bc != "":
        return (False, " bc was not able to complete the computation: " + error_bc)

    return (True, bc_result.stdout.strip())


tool_catalog = [
    {
    "name": "today",
    "description": "Returns the current date in the format of a python strftime (%y-%m-%d) ",
    "inputSchema": {
        "type": "object",
        "properties": {
            "format": {"type": "string", "description": "Enter a date format in python strftime "}
        },
        "required": ["format"]
    }
},

    {
    "name": "weekday",
    "description": " returns the name of the weekday for a given calendar date in yyyy-mm-dd format",
    "inputSchema": {
        "type": "object",
        "properties": {
            "date": {"type": "string", "description": "Give a date in the yyyy-mm-dd format, e.g. 2026-10-26"}
        },
        "required": ["date"]
    }
},

    {
    "name": "timer",
    "description": "Wait for a certain amount of time until sending an alarm while sending an udpate every 10 seconds ",
    "inputSchema": {
        "type": "object",
        "properties": {
            "alarm": {"type": "number", "description": "give the amount of seconds until the alarm with a maximum of 300 seconds, fractions are allowed. ", "minimum": 0}
        },
        "required": ["alarm"]
    }
},
    {
    "name": "calculator",
    "description": "calculate the result of a mathematical expresion using the bc calc program",
    "inputSchema": {
        "type": "object",
        "properties": {
            "expression": {"type": "string", "description": "Input the expression, e.g. 1+2 or 2^4 "}
        },
        "required": ["expression"]
    }
}
]


