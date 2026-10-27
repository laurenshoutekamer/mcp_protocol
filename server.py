from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse
import base64
import json
from tools import (run_today_tool, run_weekday_tool, run_calculator_tool, run_timer_tool, tool_catalog)


protocol_version = "2026-07-28"


server_information = {
    "resultType": "complete",
    "supportedVersions": [protocol_version],
    "capabilities": {"tools": {"listChanged": False}},
    "_meta": {"io.modelcontextprotocol/serverInfo": {"name": "server_ljh_csee4119", "version": "7"}},
    "ttlMs": 0,
    "cacheScope": "public"
}

list_result = {"resultType": "complete", "tools": tool_catalog, "ttlMs": 0, "cacheScope": "public"}


class Handler(BaseHTTPRequestHandler):
    
    did_reply_start = False

    def do_POST(self):
        try:
            self.handle_mcp_post()
        except (BrokenPipeError, ConnectionResetError):
            print(" the client did not stay connected until the reply was fully processed ")
        except Exception as prblm_instance:
            print("there was an unexpected problem on the server: " + repr(prblm_instance))
            if not self.did_reply_start:
                try:
                    self.send_jsonrpc_error(500, None, -32603, "unexpected internal error")
                except OSError:
                    pass

    def handle_mcp_post(self):
        head_val_origin = self.headers.get("Origin")
        if head_val_origin is not None:
            parsed_origin = urlparse(head_val_origin)
            host_name_origin = parsed_origin.hostname
            legal_host1 = "localhost"
            legal_host2 = "127.0.0.1"
            if host_name_origin != legal_host1 and host_name_origin != legal_host2:
                self.reply(403, {"jsonrpc": "2.0", "error": {"code": -32600, "message": "unverified origins are not allowed"}})
                return
        
        if self.path != "/mcp":
            self.reply(404, {"error": " request sent to wrong adress, the actual endpoint is /mcp"})
            return
        transfer_encoding_header = self.headers.get("Transfer-Encoding")
        
        if transfer_encoding_header is not None:
            self.reply(400, {"error": "this program only works with content length requests, transfer encoding is not accepted"})
            return
        length_content_txt = self.headers.get("Content-Length")
        
        if length_content_txt is None:
            self.reply(400, {"error": "Please provide a content length header for the server to function properly"})
            return
        
        try:
            legnth_content_val = int(length_content_txt)
        
        except ValueError:
            self.reply(400, {"error": "the content length provided was not read as a whole number"})
            return
        
        if legnth_content_val < 0:
            self.reply(400, {"error": " the body size is incorrect, make sure it is not negative"})
            return
        inc_body_bytes = self.rfile.read(legnth_content_val)
        
        if len(inc_body_bytes) < legnth_content_val:
            self.reply(400, {"error": " the server did not receive the amount of data specified in the content length, content lenght incorrect or data cut off"})
            return
        
        try:
            inc_body_txt = inc_body_bytes.decode("utf-8")
            request_obj = json.loads(inc_body_txt)
        
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.send_jsonrpc_error(400, None, -32700, "problem with parsing, the server could not read the input as a valid JSON")
            return
        request_error = check_mcp_request(request_obj, self.headers)
        
        if request_error is not None:
            status_code_reply, message_obj = request_error
            self.reply(status_code_reply, message_obj)
            return
        req_id_body = request_obj.get("id")
        req_boolean = "id" in request_obj
        
        if not req_boolean:
            self.send_accepted_empty()
            return
        req_method = request_obj.get("method")
        req_params_obj = request_obj.get("params")
        req_meta_obj = req_params_obj.get("_meta")
        
        if req_method == "server/discover":
            self.send_jsonrpc_result(req_id_body, server_information)
        elif req_method == "tools/list":
            self.send_jsonrpc_result(req_id_body, list_result)
        elif req_method == "tools/call":
            self.handle_tool_call(req_id_body, req_params_obj, req_meta_obj)
        else:
            self.send_jsonrpc_error(404, req_id_body, -32601, "the method cannot be found: " + req_method + " ")

    #examine tool request for errors run tool and send answer 
    def handle_tool_call(self, req_id_body, req_params_obj, req_meta_obj):
        #checking all possible errors of tool name
        head_name_val = self.headers.get("Mcp-Name")
        if head_name_val is None:
            self.send_jsonrpc_error(400, req_id_body, -32020, "Header problem, the mcp name header is missing for tools/call")
            return
        head_tool_name = decode_mcp_name_header(head_name_val)
        if head_tool_name is None:
            self.send_jsonrpc_error(400, req_id_body, -32020, "Header problem, the tool name is encoded in a way that the program cannot read")
            return
        body_tool_name = req_params_obj.get("name")
        if type(body_tool_name) != str:
            self.send_jsonrpc_error(400, req_id_body, -32602, "Invalid parameters, please include the name of the tool to be used as text")
            return
        if head_tool_name != body_tool_name:
            self.send_jsonrpc_error(400, req_id_body, -32020, "Header problem, the tool name in the header is mismatching with the tool name in the request")
            return
    

        tool_arg_obj = req_params_obj.get("arguments")
        # find tool

        tool_found = False
        for tool_entry in tool_catalog:
            if tool_entry["name"] == body_tool_name:
                tool_found = True
                break
        if not tool_found:
            self.send_jsonrpc_error(404, req_id_body, -32602, "This MCP server does not have this tool available: " + body_tool_name)
            return
        
    
        tracking_label_progress = req_meta_obj.get("progressToken")
        if type(tracking_label_progress) not in (str, int):
            tracking_label_progress = None
        
        #using the tool
        if type(tool_arg_obj) != dict:
            self.send_jsonrpc_error(400, req_id_body, -32602, " The inputs for the tool are not correct, correct the formatting. Provide the values inside {}. ")
            return
        elif body_tool_name == "timer":
            self.handle_timer_call(req_id_body, tool_arg_obj, tracking_label_progress)
            return
        elif body_tool_name == "today":
            tool_success, tool_answ_txt = run_today_tool(tool_arg_obj)
        elif body_tool_name == "weekday":
            tool_success, tool_answ_txt = run_weekday_tool(tool_arg_obj)
        elif body_tool_name == "calculator":
            tool_success, tool_answ_txt = run_calculator_tool(tool_arg_obj)
        
        # reply with result
        tool_result = {
            "resultType": "complete",
            "content": [{"type": "text", "text": tool_answ_txt}],
            "isError": not tool_success
        }
        self.send_jsonrpc_result(req_id_body, tool_result)

    # run the timer and handle its replies and connection errors
    def handle_timer_call(self, req_id_body, tool_arg_obj, tracking_label_progress):

        def send_update(time_elapsed_since_start, duration_alarm, seconds_left):
            if tracking_label_progress is not None:
                prgrs_notficiation = {
                    "jsonrpc": "2.0",
                    "method": "notifications/progress",
                    "params": {
                        "progressToken": tracking_label_progress,
                        "progress": time_elapsed_since_start,
                        "total": duration_alarm,
                        "message": format(seconds_left, "g") + " remaining"
                    }
                }
                self.write_sse_event(prgrs_notficiation)

        try:
            tool_success, alarm_txt = run_timer_tool(tool_arg_obj, self.start_sse_reply, send_update)

            # send result
            tool_result = {
                "resultType": "complete",
                "content": [{"type": "text", "text": alarm_txt}],
                "isError": not tool_success
            }

            if tool_success:
                self.write_sse_event({"jsonrpc": "2.0", "id": req_id_body, "result": tool_result})
            else:
                self.send_jsonrpc_result(req_id_body, tool_result)
        except OSError:
            print("The client was disconnected so the timer was stopped ")
        except Exception as prblm_instance:
            if not self.did_reply_start:
                raise
            print("there was an unexpected problem with the timer: " + repr(prblm_instance))
            try:
                error_reply_obj = {"jsonrpc": "2.0", "id": req_id_body, "error": {"code": -32603, "message": "There was an error while the timer was running"}}
                self.write_sse_event(error_reply_obj)
            except OSError:
                pass

    def send_jsonrpc_result(self, req_id, obj_result):
        body_result = {"jsonrpc": "2.0", "id": req_id, "result": obj_result}
        self.reply(200, body_result)

    def send_jsonrpc_error(self, status_code_reply, req_id, number_error_code, txt_error_code, data_val_error=None):
        self.reply(status_code_reply, build_jsonrpc_error(req_id, number_error_code, txt_error_code, data_val_error))

    def reply(self, status_code_reply, message_obj):
        self.did_reply_start = True
        bytes_json_reply = json.dumps(message_obj).encode("utf-8")
        self.send_response(status_code_reply)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(bytes_json_reply)))
        self.end_headers()
        self.wfile.write(bytes_json_reply)

    # open repsonse stream for timer updates and the final alarm
    def start_sse_reply(self):
        self.did_reply_start = True
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

    def write_sse_event(self, jsonrpc_message_obj):
    	json_event_txt = json.dumps(jsonrpc_message_obj)
    	line_txt_sse = "data: " + json_event_txt + "\n\n"
    	self.wfile.write(line_txt_sse.encode("utf-8"))
    	self.wfile.flush()

    def send_accepted_empty(self):
    	self.did_reply_start = True
    	self.send_response(202)
    	self.send_header("Content-Length", "0")
    	self.end_headers()

    #avoid get request
    def do_GET(self):
        self.reply(405, {"error": "The request reached the server wrong, method not allowed. Send the request using POST. "})

    #avoid delete request 
    def do_DELETE(self):
        self.reply(405, {"error": "The request reached the server wrong, method not allowed. Send the request using POST. "})


# check the request for any errors 
def check_mcp_request(request_obj, headers):
    if type(request_obj) != dict:
        return (400, build_jsonrpc_error(None, -32600, " Incorrect request: the server expected only one JSON object enclosed in braces {} "))
    
    if request_obj.get("jsonrpc") != "2.0":
        return (400, build_jsonrpc_error(None, -32600, "Incorrect request: the jsonrpc field must be the text 2.0"))
    req_id_body = request_obj.get("id")
    req_boolean = "id" in request_obj
    
    if req_boolean and type(req_id_body) not in (str, int):
        return (400, build_jsonrpc_error(None, -32600, "incorrect request: the id provided must be formatted as a string or integer"))
    req_method = request_obj.get("method")
    
    if type(req_method) != str:
        return (400, build_jsonrpc_error(req_id_body, -32600, "Incorrect requerst: the method must be in text, please name the requested action"))
    
    if not req_boolean:
        return None
    req_params_obj = request_obj.get("params")
    
    if type(req_params_obj) != dict:
        return (400, build_jsonrpc_error(req_id_body, -32602, "invalid paramers received, missing the params object or params object supplied with the wrong type"))
    req_meta_obj = req_params_obj.get("_meta")
    
    if type(req_meta_obj) != dict:
        return (400, build_jsonrpc_error(req_id_body, -32602, "invalid parameters received,  _meta object must be provided in the params"))
    version_value = req_meta_obj.get("io.modelcontextprotocol/protocolVersion")
    
    if type(version_value) != str:
        return (400, build_jsonrpc_error(req_id_body, -32602, "invalid parameters received: the MCP version is missing or was provided in a format other than text"))
    val_client_capabilities = req_meta_obj.get("io.modelcontextprotocol/clientCapabilities")
    
    if type(val_client_capabilities) != dict:
        return (400, build_jsonrpc_error(req_id_body, -32602, "invalid params received: the clients supported features are missing or formatted incorrectly "))
    head_v_val = headers.get("MCP-Protocol-Version")
    
    if head_v_val != version_value:
        return (400, build_jsonrpc_error(req_id_body, -32020, "Header problem, missing header of different from the version in the request"))
    
    if version_value != protocol_version:
        return (400, build_jsonrpc_error(req_id_body, -32022, "this protcol version is not supported by this MCP server", {"supported": [protocol_version], "requested": version_value}))
    head_method_val = headers.get("Mcp-Method")
    
    if head_method_val != req_method:
        return (400, build_jsonrpc_error(req_id_body, -32020, " Header problem, the MCP method header is not present or mismatched with the body"))
    return None


#decode toolname from header
def decode_mcp_name_header(header_text):
    if header_text.startswith("=?base64?") and header_text.endswith("?="):
        header_encoded = header_text[len("=?base64?"):-len("?=")]
        try:
            return base64.b64decode(header_encoded, validate=True).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return None
    return header_text

#prep error response
def build_jsonrpc_error(req_id, number_error_code, txt_error_code, data_val_error=None):
    err_body = {"jsonrpc": "2.0", "error": {"code": number_error_code, "message": txt_error_code}}
    if data_val_error is not None:
        err_body["error"]["data"] = data_val_error
    if req_id is not None:
        err_body["id"] = req_id
    return err_body


if __name__ == "__main__":
    mcp_server = HTTPServer(("127.0.0.1", 12188), Handler)
    mcp_server.serve_forever()
