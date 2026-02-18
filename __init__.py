import bpy
import json
import urllib.request
import urllib.parse
import urllib.error
import os
import uuid
import mimetypes
import time
import shutil

print("Retexturity Addon v1.4.0 Loaded")

# ------------------------------------------------------------------------
# ComfyUI API Client (using urllib to avoid external dependencies)
# ------------------------------------------------------------------------

class ComfyUIClient:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip('/')
        self.client_id = str(uuid.uuid4())

    def _request(self, endpoint, method='GET', data=None, headers=None):
        url = f"{self.base_url}{endpoint}"
        if headers is None:
            headers = {}
        
        if data is not None and method == 'POST':
            if headers.get('Content-Type') == 'application/json':
                data = json.dumps(data).encode('utf-8')
            elif not isinstance(data, bytes):
                 # Assume data is already encoded bytes if not json
                 pass

        req = urllib.request.Request(url, data=data, method=method)
        
        for k, v in headers.items():
            req.add_header(k, v)

        try:
            with urllib.request.urlopen(req) as response:
                return response.read()
        except urllib.error.URLError as e:
            print(f"ComfyUI Error: {e}")
            return None

    def check_connection(self):
        # Simple check to see if server is up, e.g. getting system stats or just root
        return self._request("/system_stats") is not None

    def queue_prompt(self, prompt, client_id=None):
        if client_id is None:
            client_id = self.client_id
        
        data = {"prompt": prompt, "client_id": client_id}
        response = self._request("/prompt", method='POST', data=data, headers={'Content-Type': 'application/json'})
        if response:
            return json.loads(response)
        return None

    def upload_image(self, filepath, subfolder="", folder_type="input"):
        # Multipart form data upload implementation using urllib
        if not os.path.exists(filepath):
            print(f"File not found: {filepath}")
            return None

        boundary = '----WebKitFormBoundary' + uuid.uuid4().hex
        headers = {'Content-Type': f'multipart/form-data; boundary={boundary}'}
        
        filename = os.path.basename(filepath)
        mime_type = mimetypes.guess_type(filepath)[0] or 'application/octet-stream'
        
        with open(filepath, 'rb') as f:
            file_content = f.read()

        body = []
        # Image part
        body.append(f'--{boundary}'.encode('utf-8'))
        body.append(f'Content-Disposition: form-data; name="image"; filename="{filename}"'.encode('utf-8'))
        body.append(f'Content-Type: {mime_type}'.encode('utf-8'))
        body.append(b'')
        body.append(file_content)
        
        # Other fields
        if subfolder:
            body.append(f'--{boundary}'.encode('utf-8'))
            body.append(b'Content-Disposition: form-data; name="subfolder"')
            body.append(b'')
            body.append(subfolder.encode('utf-8'))
            
        body.append(f'--{boundary}'.encode('utf-8'))
        body.append(b'Content-Disposition: form-data; name="type"')
        body.append(b'')
        body.append(folder_type.encode('utf-8'))
        
        body.append(f'--{boundary}--'.encode('utf-8'))
        body.append(b'')
        
        payload = b'\r\n'.join(body)
        
        response = self._request("/upload/image", method='POST', data=payload, headers=headers)
        if response:
            return json.loads(response)
        return None

    def get_history(self, prompt_id):
        response = self._request(f"/history/{prompt_id}")
        if response:
            return json.loads(response)
        return None

    def get_image(self, filename, subfolder, folder_type):
        params = urllib.parse.urlencode({
            "filename": filename,
            "subfolder": subfolder,
            "type": folder_type
        })
        return self._request(f"/view?{params}")


# ------------------------------------------------------------------------
# Addon Preferences
# ------------------------------------------------------------------------

class RetexturityAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    api_url: bpy.props.StringProperty(
        name="ComfyUI URL",
        default="http://127.0.0.1:8188",
        description="URL of the running ComfyUI instance"
    )

    output_path: bpy.props.StringProperty(
        name="Addon Output Directory",
        subtype='DIR_PATH',
        default="//retexturity_outputs/",
        description="Folder where generated files will be saved. Use // for relative to blend file."
    )

    comfyui_output_path: bpy.props.StringProperty(
        name="ComfyUI Output Directory",
        subtype='DIR_PATH',
        description="Absolute path to your ComfyUI 'output' folder (e.g. U:\\ComfyUI\\output)"
    )

    # Sound Settings
    play_sound_on_finish: bpy.props.BoolProperty(
        name="Play Sound on Finish",
        default=True,
        description="Play a sound when generation completes"
    )

    custom_sound_path: bpy.props.StringProperty(
        name="Custom Sound File",
        subtype='FILE_PATH',
        description="Path to custom sound file (wav, mp3, ogg). Leave empty for default."
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "api_url")
        layout.prop(self, "comfyui_output_path")
        layout.prop(self, "output_path")
        
        box = layout.box()
        box.label(text="Notification Settings", icon='SOUND')
        box.prop(self, "play_sound_on_finish")
        if self.play_sound_on_finish:
             box.prop(self, "custom_sound_path")

# ------------------------------------------------------------------------
# Properties
# ------------------------------------------------------------------------

def get_node_items(self, context):
    # This callback populates the EnumProperty for node selection
    items = []
    props = context.scene.retexturity_props
    
    if not props.cached_nodes_json:
        return [("NONE", "No Nodes found", "Load a workflow first")]
    
    try:
        nodes = json.loads(props.cached_nodes_json)
        # nodes dict structure: {"id": {"class_type": "...", "inputs": ...}}
        for node_id, node_data in nodes.items():
            class_type = node_data.get("class_type", "Unknown")
            # Prefer title meta > class_type
            title = node_data.get("_meta", {}).get("title", class_type)
            identifier = f"{node_id}: {title} ({class_type})"
            items.append((node_id, identifier, identifier))
            
    except Exception as e:
        print(f"Error parsing cached nodes: {e}")
        return [("ERROR", "Error parsing nodes", "Check console")]

    return items if items else [("NONE", "No Nodes found", "")]

class RetexturityNodeParam(bpy.types.PropertyGroup):
    node_id: bpy.props.StringProperty()
    node_title: bpy.props.StringProperty()
    param_name: bpy.props.StringProperty()
    
    # Type identifier: 'INT', 'FLOAT', 'STRING', 'BOOL'
    value_type: bpy.props.StringProperty() 
    
    # Values
    int_val: bpy.props.IntProperty()
    float_val: bpy.props.FloatProperty()
    str_val: bpy.props.StringProperty()
    bool_val: bpy.props.BoolProperty()
    
    # For Image Params
    image_path: bpy.props.StringProperty(
        subtype='FILE_PATH',
        description="Select image file to upload to ComfyUI"
    )

class RetexturityNodeState(bpy.types.PropertyGroup):
    node_id: bpy.props.StringProperty()
    node_title: bpy.props.StringProperty()
    group_name: bpy.props.StringProperty() # For grouping in UI
    is_expanded: bpy.props.BoolProperty(default=True)

class RetexturityProperties(bpy.types.PropertyGroup):
    # We use the preferences for URL, but keep a property here if user wants to override per scene?
    # For now, let's just read from prefs in operators to avoid confusion.
    # But UI needs to show something. Let's redirect UI to prefs.
    
    workflow_file: bpy.props.StringProperty(
        name="Workflow JSON",
        subtype='FILE_PATH',
        description="Path to the API-formatted ComfyUI workflow JSON"
    )

    workflow_list: bpy.props.EnumProperty(
        name="Select Workflow",
        description="Select a workflow from the addons 'workflows' folder",
        items=get_workflow_items,
        update=update_workflow_list
    )
    
    # Internal storage for the loaded JSON structure stringified
    cached_nodes_json: bpy.props.StringProperty()
    full_workflow_json: bpy.props.StringProperty()

    input_node_id: bpy.props.EnumProperty(
        name="Input Node",
        description="Select the 'Load Image' node to receive Blender's render",
        items=get_node_items
    )
    
    output_node_id: bpy.props.EnumProperty(
        name="Output Node",
        description="Select the 'Save' node that produces the result (Mesh or Image)",
        items=get_node_items
    )
    
    # Collection of Exposed Parameters
    node_params: bpy.props.CollectionProperty(type=RetexturityNodeParam)
    
    # Collection of Node UI States (Collapsible)
    node_states: bpy.props.CollectionProperty(type=RetexturityNodeState)

    is_generating: bpy.props.BoolProperty(
        name="Is Generating",
        default=False
    )
    
    # Stores the path to the pending result for manual import
    latest_generated_filepath: bpy.props.StringProperty(
        subtype='FILE_PATH'
    )

# ------------------------------------------------------------------------
# Operators
# ------------------------------------------------------------------------

def load_workflow_common(context, filepath):
    props = context.scene.retexturity_props
    
    if not filepath or not os.path.exists(filepath):
        return False, "Workflow file not found"
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            workflow = json.load(f)
        
        # Basic validation
        valid = True
        if not isinstance(workflow, dict):
            valid = False
        else:
            for k, v in workflow.items():
                if "class_type" not in v or "inputs" not in v:
                    valid = False
                    break
        
        if not valid:
            return False, "Invalid API Format. Please use 'Save (API Format)' in ComfyUI Dev Mode."

        # Populate Parameters
        props.node_params.clear()
        props.node_states.clear()
        
        # Blacklist for UI
        blacklist_titles = ["Preview 3D", "Preview 3D & Animation", "Animation"]
        
        for node_id, node_data in workflow.items():
            title = node_data.get("_meta", {}).get("title", node_data.get("class_type", ""))
            
            # Filter Blacklisted Nodes
            if any(x in title for x in blacklist_titles):
                continue

            # Add Node State (for UI collapsing)
            state_item = props.node_states.add()
            state_item.node_id = node_id
            
            # Check for Group Name in Title (fmt: "Group : Title" or "Group | Title")
            group_name = ""
            clean_title = title
            
            # Simple parser
            if " : " in title:
                parts = title.split(" : ", 1)
                if len(parts) == 2:
                    group_name = parts[0].strip()
                    clean_title = parts[1].strip()
            elif " | " in title:
                parts = title.split(" | ", 1)
                if len(parts) == 2:
                    group_name = parts[0].strip()
                    clean_title = parts[1].strip()
            
            state_item.node_title = clean_title
            state_item.group_name = group_name
            state_item.is_expanded = False # Default collapsed for cleaner UI? Or True? Let's say False to save space.

            inputs = node_data.get("inputs", {})
            
            for param_name, param_value in inputs.items():
                # Check if it's a primitive value (not a link like ["5", 0])
                if not isinstance(param_value, list):
                    # Determine type
                    start_type = None
                    
                    # Check specific key names for Image Inputs
                    valid_img_keys = ['image', 'image_path', 'filename']
                    if param_name in valid_img_keys and isinstance(param_value, str):
                        start_type = 'IMAGE'
                    elif isinstance(param_value, bool):
                        start_type = 'BOOL'
                    elif isinstance(param_value, int):
                        start_type = 'INT'
                    elif isinstance(param_value, float):
                        start_type = 'FLOAT'
                    elif isinstance(param_value, str):
                        start_type = 'STRING'
                    
                    if start_type:
                        item = props.node_params.add()
                        item.node_id = node_id
                        item.node_title = title
                        item.param_name = param_name
                        item.value_type = start_type
                        
                        if start_type == 'BOOL':
                            item.bool_val = param_value
                        elif start_type == 'INT':
                            item.int_val = param_value
                        elif start_type == 'FLOAT':
                            item.float_val = param_value
                        elif start_type == 'STRING':
                            item.str_val = param_value
                        elif start_type == 'IMAGE':
                            # Don't set default unless it's a path, usually it's just a filename.
                            # Let user pick.
                            pass

        # Store for usage
        props.full_workflow_json = json.dumps(workflow)
        props.cached_nodes_json = json.dumps(workflow)
        
        # Try to auto-select likely candidates
        input_cand = None
        output_cand = None
        
        for node_id, node_data in workflow.items():
            class_type = node_data.get("class_type", "").lower()
            title = node_data.get("_meta", {}).get("title", "").lower()
            inputs = node_data.get("inputs", {})

            # Heuristic for Input (Image Load)
            if "loadimage" in class_type or "load image" in title:
                    input_cand = node_id
            
            # Heuristic for Output (Save or Export)
            if "save" in class_type or "export" in class_type or "preview" in class_type:
                output_cand = node_id
                # Prioritize Trellis Export Mesh if found
                if "trellis" in class_type and "export" in class_type:
                    output_cand = node_id

        if input_cand:
            props.input_node_id = input_cand
        if output_cand:
            props.output_node_id = output_cand
        
        return True, f"Loaded workflow with {len(workflow)} nodes"
        
    except Exception as e:
        return False, f"Failed to load JSON: {str(e)}"

class RETEXTURITY_OT_load_workflow(bpy.types.Operator):
    """Load and parse the ComfyUI API Workflow JSON from manual file selection"""
    bl_idname = "retexturity.load_workflow"
    bl_label = "Load Workflow"
    
    def execute(self, context):
        props = context.scene.retexturity_props
        filepath = props.workflow_file
        
        success, msg = load_workflow_common(context, filepath)
        if success:
            self.report({'INFO'}, msg)
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, msg)
            return {'CANCELLED'}

def get_workflow_items(self, context):
    items = [("NONE", "Select a Workflow...", "")]
    
    # Define workflows directory
    addon_dir = os.path.dirname(__file__)
    wf_dir = os.path.join(addon_dir, "workflows")
    
    if os.path.exists(wf_dir):
        for f in os.listdir(wf_dir):
            if f.endswith(".json"):
                # Use filename as ID and Label
                items.append((f, f, f"Load {f}"))
    
    return items

def update_workflow_list(self, context):
    if self.workflow_list == "NONE":
        return
        
    addon_dir = os.path.dirname(__file__)
    filepath = os.path.join(addon_dir, "workflows", self.workflow_list)
    
    success, msg = load_workflow_common(context, filepath)
    if success:
        # Also update the manual file path for consistency? Or clear it?
        # Let's set it so the user knows what's loaded
        self.workflow_file = filepath
    else:
        print(f"[Retexturity] Auto-load failed: {msg}")

class RETEXTURITY_OT_generate(bpy.types.Operator):
    """Send render to ComfyUI and retrieve result (Non-Blocking)"""
    bl_idname = "retexturity.generate"
    bl_label = "Generate"
    
    _timer = None
    _prompt_id = None
    _client = None
    _start_time = 0
    
    def execute(self, context):
        self._start_time = time.time()
        props = context.scene.retexturity_props
        
        # Check if already running
        if props.is_generating:
             self.report({'WARNING'}, "Already generating...")
             return {'CANCELLED'}

        # Get URL from Preferences
        prefs = context.preferences.addons[__package__].preferences
        api_url = prefs.api_url
        
        self._client = ComfyUIClient(api_url)
        
        # 1. Check Connection
        if not self._client.check_connection():
            self.report({'ERROR'}, f"Could not connect to ComfyUI at {api_url}. Check Preferences.")
            return {'CANCELLED'}

        if not props.full_workflow_json:
            self.report({'ERROR'}, "No workflow loaded.")
            return {'CANCELLED'}

        if not props.full_workflow_json:
            self.report({'ERROR'}, "No workflow loaded.")
            return {'CANCELLED'}
        
        # CHECK FOR LOCAL IMAGE PARAMS
        has_manual_images = False
        workflow = json.loads(props.full_workflow_json)
        
        for p in props.node_params:
            if p.value_type == 'IMAGE' and p.image_path and os.path.exists(p.image_path):
                has_manual_images = True
                break
        
        uploaded_filename = None
        uploaded_subfolder = ""
        uploaded_type = "input"

        # 2. Render OR Upload Manual Images
        if not has_manual_images:
            # LEGACY FLOW: Render Scene
            temp_dir = bpy.app.tempdir
            render_path = os.path.join(temp_dir, "retexturity_input.png")
            
            # Save current settings
            prev_filepath = context.scene.render.filepath
            prev_format = context.scene.render.image_settings.file_format
            
            try:
                context.scene.render.filepath = render_path
                context.scene.render.image_settings.file_format = 'PNG'
                bpy.ops.render.render(write_still=True)
            finally:
                # Restore settings
                context.scene.render.filepath = prev_filepath
                context.scene.render.image_settings.file_format = prev_format
    
            if not os.path.exists(render_path):
                 self.report({'ERROR'}, "Render failed.")
                 return {'CANCELLED'}
    
            # 3. Upload Render
            self.report({'INFO'}, "Uploading render...")
            upload_resp = self._client.upload_image(render_path, subfolder="") 
            if not upload_resp:
                self.report({'ERROR'}, "Failed to upload render.")
                return {'CANCELLED'}
            
            uploaded_filename = upload_resp.get("name")
            uploaded_subfolder = upload_resp.get("subfolder", "")
            uploaded_type = upload_resp.get("type", "input")
            
            # Update Input Node (Legacy)
            input_id = props.input_node_id
            if input_id in workflow:
                node_inputs = workflow[input_id].get("inputs", {})
                image_key = None
                if "image" in node_inputs: image_key = "image"
                elif "filename" in node_inputs: image_key = "filename"
                elif "image_path" in node_inputs: image_key = "image_path"
                
                if image_key:
                    node_inputs[image_key] = uploaded_filename
                    node_inputs["subfolder"] = uploaded_subfolder
                    node_inputs["type"] = uploaded_type
                else:
                    node_inputs["image"] = uploaded_filename
                    node_inputs["subfolder"] = uploaded_subfolder
                    node_inputs["type"] = uploaded_type

        else:
             self.report({'INFO'}, "Using manual images (skipping render)...")

        # 4. INJECT PARAMETERS (and Upload Manual Images)
        for param in props.node_params:
            if param.node_id in workflow:
                # Update value based on type
                new_val = None
                
                if param.value_type == 'IMAGE':
                    # Upload if valid path
                    if param.image_path and os.path.exists(param.image_path):
                         print(f"[Retexturity] Uploading manual image: {param.image_path}")
                         resp = self._client.upload_image(param.image_path)
                         if resp:
                             new_val = resp.get("name")
                             # Note: If node needs subfolder/type, we assume default or inject if key exists?
                             # For simplicity, we just inject filename. Most nodes handle root.
                elif param.value_type == 'INT':
                    new_val = param.int_val
                elif param.value_type == 'FLOAT':
                    new_val = param.float_val
                elif param.value_type == 'STRING':
                    new_val = param.str_val
                elif param.value_type == 'BOOL':
                    new_val = param.bool_val
                
                if new_val is not None:
                    workflow[param.node_id]["inputs"][param.param_name] = new_val

        # 5. Queue Prompt
        self.report({'INFO'}, "Queuing prompt...")

        # 5. Queue Prompt
        self.report({'INFO'}, "Queuing prompt...")
        prompt_resp = self._client.queue_prompt(workflow)
        if not prompt_resp or "prompt_id" not in prompt_resp:
             self.report({'ERROR'}, "Failed to queue prompt.")
             return {'CANCELLED'}
        
        self._prompt_id = prompt_resp['prompt_id']
        self.report({'INFO'}, f"Prompt queued: {self._prompt_id}. Waiting for result...")
        
        # Start Modal Timer
        props.is_generating = True
        wm = context.window_manager
        # Check every 2 seconds to avoid spamming connection
        self._timer = wm.event_timer_add(2.0, window=context.window)
        wm.modal_handler_add(self)
        
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        props = context.scene.retexturity_props
        
        if not props.is_generating:
            return self.cancel(context)
        
        if event.type == 'TIMER':
            # Check status
            print(f"[Retexturity] Checking history for {self._prompt_id}...")
            try:
                history_data = self._client.get_history(self._prompt_id)
            except Exception as e:
                print(f"[Retexturity] Error connecting to history: {e}")
                history_data = None

            if history_data and self._prompt_id in history_data:
                print(f"[Retexturity] History found for {self._prompt_id}!")
                # Finished! Handle result
                try:
                    self.handle_result(context, history_data)
                except Exception as e:
                    self.report({'ERROR'}, f"Error handling result: {e}")
                    import traceback
                    traceback.print_exc()
                
                # Cleanup
                return self.cancel(context)
            else:
                # Still running or not found yet
                pass
                
        return {'PASS_THROUGH'}

    def handle_result(self, context, history_data):
        props = context.scene.retexturity_props
        
        # Debugging Response
        prompt_data = history_data[self._prompt_id]
        if "outputs" not in prompt_data:
             print(f"[Retexturity] WARNING: 'outputs' key missing in history for {self._prompt_id}. Data keys: {prompt_data.keys()}")
             return

        outputs = prompt_data.get("outputs", {})
        print(f"[Retexturity] Outputs keys: {list(outputs.keys())}")
        
        output_id = props.output_node_id
        print(f"[Retexturity] Expected Output Node ID: {output_id}")
        
        target_file = None
        source_path = None
        fname = None
        
        # 1. Try to get file from History API
        if output_id in outputs:
            node_output = outputs[output_id]
            print(f"[Retexturity] Output Data for {output_id}: {node_output}")
            
            valid_keys = ['images', 'gifs', 'files', 'meshes']
            for key in valid_keys:
                if key in node_output and len(node_output[key]) > 0:
                    target_file = node_output[key][0]
                    print(f"[Retexturity] Found target file in key '{key}': {target_file}")
                    break
        
        # 2. If API failed (silent node), try Fallback: Scan Output Folder for latest file
        prefs = context.preferences.addons[__package__].preferences
        comfyui_output_dir_pref = prefs.comfyui_output_path
        
        if not target_file:
            print(f"[Retexturity] Target node {output_id} not in history outputs.")
            
            if comfyui_output_dir_pref and os.path.exists(comfyui_output_dir_pref):
                 print(f"[Retexturity] Attempting fallback: Scaning {comfyui_output_dir_pref} for recent files...")
                 # Find latest file
                 latest_file = None
                 latest_time = 0
                 
                 # Scan for specific extensions to be safe
                 valid_exts = ['.glb', '.gltf', '.obj', '.png', '.jpg', '.exr']
                 
                 for f in os.listdir(comfyui_output_dir_pref):
                     fp = os.path.join(comfyui_output_dir_pref, f)
                     if os.path.isfile(fp):
                         ext = os.path.splitext(f)[1].lower()
                         if ext in valid_exts:
                             mtime = os.path.getmtime(fp)
                             if mtime > latest_time:
                                 latest_time = mtime
                                 latest_file = fp
                 
                 # Check if it was created AFTER we started
                 # Giving a small buffer (e.g. -1s) just in case of clock skew, though unlikely on same machine
                 if latest_file and latest_time >= (self._start_time - 1.0):
                     print(f"[Retexturity] Fallback SUCCESS. Found recent file: {latest_file}")
                     source_path = latest_file
                     fname = os.path.basename(latest_file)
                     # We have a source path directly now
                 else:
                     print(f"[Retexturity] Fallback Failed. No new files found. Latest was {latest_file} at {latest_time} (Job start: {self._start_time})")
            else:
                 print(f"[Retexturity] No ComfyUI Output Path configured for fallback.")

        # 3. Construct Source/Dest if we got it from API
        if target_file and "filename" in target_file:
            fname = target_file.get("filename")
            sub = target_file.get("subfolder", "")
            ftype = target_file.get("type", "output")
            # Logic continues below...
            
        if not fname and not source_path:
             print(f"[Retexturity] ERROR: Could not determine result file from API or Fallback.")
             self.report({'WARNING'}, "Could not determine result file. Check console.")
             return

        self.report({'INFO'}, f"Processing result: {fname}")
        print(f"[Retexturity] Processing result for file: {fname}")
        
        addon_output_dir_pref = prefs.output_path
        addon_output_dir = os.path.abspath(bpy.path.abspath(addon_output_dir_pref))
        if not os.path.exists(addon_output_dir):
            os.makedirs(addon_output_dir)

        # If we didn't get source_path from fallback, try to build it from API data
        if not source_path and comfyui_output_dir_pref:
             comfyui_output_dir_abs = os.path.abspath(bpy.path.abspath(comfyui_output_dir_pref))
             if os.path.exists(comfyui_output_dir_abs):
                if sub:
                    source_path = os.path.join(comfyui_output_dir_abs, sub, fname)
                else:
                    source_path = os.path.join(comfyui_output_dir_abs, fname)
                
                # Check existence
                if not os.path.exists(source_path):
                     print(f"[Retexturity] File from API not found at {source_path}")
                     # Wait loop logic was here...
        
        # ... logic merges here ...
        
        # Destination Path
        dest_path = os.path.join(addon_output_dir, f"{fname}")
        if os.path.exists(dest_path):
                name, ext = os.path.splitext(fname)
                dest_path = os.path.join(addon_output_dir, f"{name}_{int(time.time())}{ext}")

        final_path = None
        
        if source_path and os.path.exists(source_path):
            # Copy local function
            try:
                print(f"[Retexturity] Copying {source_path} -> {dest_path}")
                shutil.copy2(source_path, dest_path)
                self.report({'INFO'}, f"Copied to: {dest_path}")
                final_path = dest_path
            except Exception as e:
                print(f"[Retexturity] Copy FAILED: {e}")
                self.report({'ERROR'}, f"Failed to copy: {e}")
                return
        elif target_file:
             # Try API download if we have target_file data but no local source_path found
             # ...
             pass # Existing API fallback logic
             
             # Re-implementing simplified flow to handle both cases efficiently without duplicate code
             # Let's replace the block below entirely
        
        # REFACTORED BLOCK START
        if final_path:
             pass # Already copied
        elif target_file:
             # Fallback to API
             print(f"[Retexturity] Trying API download for {fname}")
             raw_data = self._client.get_image(fname, sub, ftype)
             if raw_data:
                with open(dest_path, 'wb') as f:
                    f.write(raw_data)
                self.report({'INFO'}, f"Downloaded to: {dest_path}")
                final_path = dest_path
        
                self.report({'INFO'}, f"Downloaded to: {dest_path}")
                final_path = dest_path
        
        if final_path:
            # 1. Store path for UI
            props.latest_generated_filepath = final_path
            
            # 2. Play Sound
            if prefs.play_sound_on_finish:
                try:
                    import aud
                    device = aud.Device()
                    sound_file = prefs.custom_sound_path
                    
                    if not sound_file or not os.path.exists(sound_file):
                         # Default
                         addon_dir = os.path.dirname(__file__)
                         sound_file = os.path.join(addon_dir, "sounds", "sound.wav")
                    
                    if os.path.exists(sound_file):
                        sound = aud.Sound(sound_file)
                        handle = device.play(sound)
                    else:
                        print(f"[Retexturity] Sound file not found: {sound_file}")

                except Exception as e:
                    print(f"[Retexturity] Failed to play sound: {e}")

            self.report({'INFO'}, "Generation Complete! See panel to Import.")
        else:
            self.report({'ERROR'}, "Failed to retrieve file via Copy or Download.")


    def cancel(self, context):
        props = context.scene.retexturity_props
        props.is_generating = False
        wm = context.window_manager
        if self._timer:
            wm.event_timer_remove(self._timer)
            self._timer = None
        return {'FINISHED'}

class RETEXTURITY_OT_import_result(bpy.types.Operator):
    """Import the generated model into the scene"""
    bl_idname = "retexturity.import_result"
    bl_label = "Import Result"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        props = context.scene.retexturity_props
        filepath = props.latest_generated_filepath
        
        if not filepath or not os.path.exists(filepath):
            self.report({'ERROR'}, "File not found.")
            return {'CANCELLED'}

        print(f"[Retexturity] Importing: {filepath}")
        fname = os.path.basename(filepath)
        
        # DESELECT ALL
        try:
            bpy.ops.object.select_all(action='DESELECT')
        except:
            pass

        # Load Logic
        ext = os.path.splitext(fname)[1].lower()
        if ext in ['.png', '.jpg', '.jpeg', '.tga', '.exr']:
            try:
                loaded_img = bpy.data.images.load(filepath)
                self.report({'INFO'}, f"Generated image loaded: {loaded_img.name}")
            except Exception as e:
                print(f"[Retexturity] Failed to load image: {e}")
                self.report({'ERROR'}, f"Could not load image into Blender: {e}")
        
        elif ext in ['.glb', '.gltf']:
            try:
                bpy.ops.import_scene.gltf(filepath=filepath)
                self.report({'INFO'}, f"Imported GLB: {fname}")
                for obj in context.selected_objects:
                    obj.select_set(True)
                    context.view_layer.objects.active = obj
            except Exception as e:
                print(f"[Retexturity] Failed to import GLB: {e}")
                self.report({'ERROR'}, f"Failed to import GLB: {e}")
                import traceback
                traceback.print_exc()
        
        elif ext in ['.obj']:
            try:
                if hasattr(bpy.ops.wm, "obj_import"):
                    bpy.ops.wm.obj_import(filepath=filepath)
                else:
                    bpy.ops.import_scene.obj(filepath=filepath)
                self.report({'INFO'}, f"Imported OBJ: {fname}")
                for obj in context.selected_objects:
                    obj.select_set(True)
                    context.view_layer.objects.active = obj
            except Exception as e:
                    print(f"[Retexturity] Failed to import OBJ: {e}")
                    self.report({'ERROR'}, f"Failed to import OBJ: {e}")
        else:
            print(f"[Retexturity] Unknown file type for auto-load: {ext}")
            self.report({'INFO'}, f"File saved to: {filepath} (Type unknown to auto-load)")
            
        # Clear property after import? Up to user preference, but usually yes.
        props.latest_generated_filepath = ""
            
        return {'FINISHED'}

class RETEXTURITY_OT_discard_result(bpy.types.Operator):
    """Discard the generated result"""
    bl_idname = "retexturity.discard_result"
    bl_label = "Discard"
    
    def execute(self, context):
        props = context.scene.retexturity_props
        props.latest_generated_filepath = ""
        return {'FINISHED'}

class RETEXTURITY_OT_cancel(bpy.types.Operator):
    """Cancel the current generation process"""
    bl_idname = "retexturity.cancel"
    bl_label = "Cancel Generation"
    
    def execute(self, context):
        props = context.scene.retexturity_props
        # This operator just sets the flag, the modal op ensures cleanup if it reads it?
        # Actually modal op holds the timer. We can't easily kill it from outside without shared state or brute force.
        # But wait, modal op checks 'TIMER'. It doesn't check 'is_generating' actively for cancellation unless we tell it.
        # Actually simplest way: just set is_generating to False, and modal will see it?
        # No, 'self' instance in modal is not accessible here easily.
        # BUT: The modal operator returns running modal. 
        # For valid cancellation, the modal needs to check a prop.
        
        # Let's verify if user can click this button while modal is blocking? 
        # Wait, if modal is RUNNING_MODAL with PASS_THROUGH, UI IS interactive!
        # So yes, user can click this button.
        
        props.is_generating = False
        return {'FINISHED'}
# We need to update modal to check props.is_generating



# ------------------------------------------------------------------------
# Panel
# ------------------------------------------------------------------------

class RETEXTURITY_OT_open_folder(bpy.types.Operator):
    """Open the output folder in file explorer"""
    bl_idname = "retexturity.open_folder"
    bl_label = "Open Output Folder"

    def execute(self, context):
        prefs = context.preferences.addons[__package__].preferences
        output_dir = bpy.path.abspath(prefs.output_path)
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        bpy.ops.wm.path_open(filepath=output_dir)
        return {'FINISHED'}

def draw_node_ui(layout, state, props):
    # Draw Collapsible Header
    box = layout.box()
    row = box.row()
    row.prop(state, "is_expanded", 
             icon="TRIA_DOWN" if state.is_expanded else "TRIA_RIGHT", 
             icon_only=True, emboss=False)
    row.label(text=state.node_title, icon='NODE')
    
    if state.is_expanded:
        # Draw Params for this node
        col = box.column(align=True)
        for param in props.node_params:
            if param.node_id == state.node_id:
                if param.value_type == 'INT':
                    col.prop(param, "int_val", text=param.param_name)
                elif param.value_type == 'FLOAT':
                    col.prop(param, "float_val", text=param.param_name)
                elif param.value_type == 'STRING':
                    col.prop(param, "str_val", text=param.param_name)
                elif param.value_type == 'BOOL':
                    col.prop(param, "bool_val", text=param.param_name)
                elif param.value_type == 'IMAGE':
                    col.prop(param, "image_path", text=param.param_name)

class RETEXTURITY_PT_main(bpy.types.Panel):
    bl_label = "UliImageTo3D"
    bl_idname = "RETEXTURITY_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Retexturity'

    def draw(self, context):
        layout = self.layout
        props = context.scene.retexturity_props
        prefs = context.preferences.addons[__package__].preferences
        
        # Display URL as read-only label or info
        layout.label(text=f"API: {prefs.api_url}")
        
        box = layout.box()
        box.label(text="Workflow Setup")
        
        # New Dropdown
        box.prop(props, "workflow_list")
        
        # Manual Override (collapsed or just below)
        row = box.row()
        row.prop(props, "workflow_file", text="")
        row.operator("retexturity.load_workflow", icon='FILE_REFRESH', text="")
        
        if props.cached_nodes_json:
            box.prop(props, "input_node_id")
            box.prop(props, "output_node_id")
            
            layout.separator()
            
            layout.separator()
            
            # Node Parameters Section
            if len(props.node_params) > 0:
                layout.label(text="Workflow Parameters", icon='NODETREE')
                
                # 1. Identify Groups
                groups = {} # name -> [state_item, ...]
                ungrouped = []
                
                for state in props.node_states:
                    # Filter out empty param nodes first?
                    # Check if this node has any params
                    has_params = False
                    for p in props.node_params:
                        if p.node_id == state.node_id:
                            has_params = True
                            break
                    
                    if not has_params:
                        continue
                        
                    if state.group_name:
                        if state.group_name not in groups:
                            groups[state.group_name] = []
                        groups[state.group_name].append(state)
                    else:
                        ungrouped.append(state)
                
                # 2. Draw Groups
                for g_name in sorted(groups.keys()):
                    group_box = layout.box()
                    group_box.label(text=f"Group: {g_name}", icon='COLLECTION_NEW')
                    
                    # Indent content slightly?
                    col_group = group_box.column() 
                    
                    for state in groups[g_name]:
                        draw_node_ui(col_group, state, props)
                
                # 3. Draw Ungrouped
                if ungrouped:
                    if groups:
                        layout.separator()
                        layout.label(text="Ungrouped Nodes:")
                        
                    for state in ungrouped:
                         draw_node_ui(layout, state, props)

                layout.separator()

            if props.is_generating:
                layout.operator("retexturity.cancel", icon='CANCEL', text="Generating... (Click to Cancel)")
            elif props.latest_generated_filepath:
                # Show Result Actions
                box_res = layout.box()
                box_res.label(text="Generation Complete!", icon='CHECKMARK')
                fname = os.path.basename(props.latest_generated_filepath)
                box_res.label(text=fname)
                
                row_res = box_res.row()
                row_res.operator("retexturity.import_result", icon='IMPORT', text="Import Result")
                row_res.operator("retexturity.discard_result", icon='TRASH', text="Discard")
            else:
                layout.operator("retexturity.generate", icon='RENDER_RESULT')
            
            layout.separator()
            layout.operator("retexturity.open_folder", icon='FILE_FOLDER')

# ------------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------------

classes = (
    RetexturityAddonPreferences,
    RetexturityNodeState,
    RetexturityNodeParam,
    RetexturityProperties,
    RETEXTURITY_OT_load_workflow,
    RETEXTURITY_OT_generate,
    RETEXTURITY_OT_cancel,
    RETEXTURITY_OT_import_result,
    RETEXTURITY_OT_discard_result,
    RETEXTURITY_OT_open_folder,
    RETEXTURITY_PT_main,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.retexturity_props = bpy.props.PointerProperty(type=RetexturityProperties)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.retexturity_props

if __name__ == "__main__":
    register()
