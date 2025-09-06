"""
AppleScript Subagent Handler - Mac Automation Implementation

This handler generates and executes AppleScript code with full user approval workflow.
It maintains internal context of all attempts and provides comprehensive feedback loops.
"""

import os
import subprocess
from typing import Dict, Any, List, Optional
from openai import OpenAI
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables from parent directory
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

class TaskVerification(BaseModel):
    accomplished: bool
    summary: str

class AppleScriptHandler:
    def __init__(self):
        self.openai_client = OpenAI()
        self.internal_context = {
            "proposed_scripts": [],
            "user_approvals": [],
            "user_feedback": [],
            "executed_scripts": [],
            "execution_outputs": [],
            "llm_assessments": [],
            "user_confirmations": [],
            "failure_reasons": []
        }
    
    def _add_to_internal_context(self, category: str, data: Any) -> None:
        """Add data to the appropriate internal context category."""
        if category in self.internal_context:
            self.internal_context[category].append(data)
            print(f"[DEBUG] Added to {category}: {len(self.internal_context[category])} items")
    
    def _get_multiline_input(self, prompt: str) -> str:
        """Get multi-line input from user, handling pasted content."""
        print(prompt + " (Press Enter twice when done, or paste and press Enter once):")
        
        lines = []
        consecutive_empty = 0
        
        while True:
            try:
                line = input()
                if line == "":
                    consecutive_empty += 1
                    if consecutive_empty >= 2:  # Two consecutive empty lines = done
                        break
                else:
                    consecutive_empty = 0
                    lines.append(line)
            except EOFError:
                break
        
        return "\n".join(lines).strip()
    
    def _get_context_summary(self) -> str:
        """Generate a summary of internal context for LLM."""
        context_parts = []
        
        if self.internal_context["proposed_scripts"]:
            context_parts.append("Previous AppleScript attempts:")
            for i, script in enumerate(self.internal_context["proposed_scripts"]):
                approval = self.internal_context["user_approvals"][i] if i < len(self.internal_context["user_approvals"]) else "pending"
                feedback = self.internal_context["user_feedback"][i] if i < len(self.internal_context["user_feedback"]) else ""
                context_parts.append(f"Attempt {i+1}: {script}")
                context_parts.append(f"User approved: {approval}")
                if feedback:
                    context_parts.append(f"User feedback: {feedback}")
        
        if self.internal_context["executed_scripts"]:
            context_parts.append("\nExecuted scripts and results:")
            for i, script in enumerate(self.internal_context["executed_scripts"]):
                output = self.internal_context["execution_outputs"][i] if i < len(self.internal_context["execution_outputs"]) else ""
                assessment = self.internal_context["llm_assessments"][i] if i < len(self.internal_context["llm_assessments"]) else ""
                context_parts.append(f"Script: {script}")
                context_parts.append(f"Output: {output}")
                context_parts.append(f"LLM assessment: {assessment}")
        
        if self.internal_context["failure_reasons"]:
            context_parts.append("\nPrevious failure reasons:")
            for reason in self.internal_context["failure_reasons"]:
                context_parts.append(f"- {reason}")
        
        return "\n".join(context_parts)
    
    def _generate_applescript(self, prompt: str, context: str) -> Optional[str]:
        """Generate AppleScript using OpenAI with internal context."""
        try:
            context_summary = self._get_context_summary()
            full_context = f"Task prompt: {prompt}\nExternal context: {context}"
            
            if context_summary:
                full_context += f"\n\nInternal context from previous attempts:\n{context_summary}"
            
            response = self.openai_client.responses.create(
                model="gpt-5",
                input=[
                    {
                        "role": "system",
                        "content": "Generate AppleScript code to accomplish the given task. Consider all previous attempts and feedback. Return only the AppleScript code, no explanations or markdown formatting. The script must be compatible with macOS. If you need to send an iMessage, you can follow this format: open contacts, select the first person whose name is the name of the person you need to message, select their first phone number, and then open messages, set the target service to the 1st service of type imessage, set the target buddy to the phone number from contacts, and send them the message."
                    },
                    {
                        "role": "user",
                        "content": full_context
                    }
                ]
            )
            
            script = response.output_text
            # Clean up any code block markers
            # if script.startswith('```'):
            #     lines = script.split('\n')
            #     script = '\n'.join(lines[1:-1]) if len(lines) > 2 else script
            
            self._add_to_internal_context("proposed_scripts", script)
            return script
            
        except Exception as e:
            print(f"Error generating AppleScript: {e}")
            return None
    
    def _get_user_script_approval(self, script: str, prompt: str, context: str) -> tuple[bool, Optional[str]]:
        """Get user approval for AppleScript with feedback collection and regeneration."""
        current_script = script
        
        while True:
            print(f"\n{'='*50}")
            print(f"APPLESCRIPT FOR TASK: {prompt}")
            print(f"{'='*50}")
            print(current_script)
            print(f"{'='*50}")
            
            approval = input("\nApprove this AppleScript? (y/n): ").strip().lower()
            
            if approval in ['y', 'yes']:
                self._add_to_internal_context("user_approvals", True)
                return True, current_script
            elif approval in ['n', 'no']:
                self._add_to_internal_context("user_approvals", False)
                feedback = input("What's wrong with this script? ").strip()
                if feedback:
                    self._add_to_internal_context("user_feedback", feedback)
                    print(f"Regenerating script based on feedback: {feedback}")
                    
                    # Regenerate script with feedback
                    new_script = self._generate_applescript(prompt, context)
                    if new_script:
                        current_script = new_script
                        continue
                    else:
                        print("Failed to regenerate script")
                        return False, feedback
                else:
                    self._add_to_internal_context("user_feedback", "No specific feedback provided")
                    return False, None
            else:
                print("Please answer 'y' for yes or 'n' for no.")
    
    def _execute_applescript(self, script: str) -> Dict[str, Any]:
        """Execute AppleScript via osascript."""
        try:
            print(f"\n🔧 Executing AppleScript...")
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            execution_result = {
                'success': result.returncode == 0,
                'output': result.stdout + result.stderr,
                'return_code': result.returncode
            }
            
            self._add_to_internal_context("executed_scripts", script)
            self._add_to_internal_context("execution_outputs", execution_result['output'])
            
            print(f"Script executed with return code: {result.returncode}")
            if execution_result['output']:
                print(f"Output: {execution_result['output']}")
            
            return execution_result
            
        except subprocess.TimeoutExpired:
            error_result = {'success': False, 'output': 'Script execution timed out', 'return_code': -1}
            self._add_to_internal_context("executed_scripts", script)
            self._add_to_internal_context("execution_outputs", error_result['output'])
            return error_result
        except Exception as e:
            error_result = {'success': False, 'output': str(e), 'return_code': -1}
            self._add_to_internal_context("executed_scripts", script)
            self._add_to_internal_context("execution_outputs", error_result['output'])
            return error_result
    
    def _verify_task_completion(self, prompt: str, script: str, execution_result: Dict[str, Any]) -> TaskVerification:
        """Get LLM verification of task completion."""
        try:
            verification_prompt = f"""
Task: {prompt}
AppleScript executed: {script}
Execution successful: {execution_result['success']}
Execution output: {execution_result['output']}
Return code: {execution_result['return_code']}

Based on the task, script, and execution results, determine if the task was accomplished successfully.
"""
            
            response = self.openai_client.responses.parse(
                model="gpt-4o-2024-08-06",
                input=[
                    {
                        "role": "system",
                        "content": "Analyze if the AppleScript execution completed the requested task successfully. Provide a boolean result and a summary."
                    },
                    {
                        "role": "user",
                        "content": verification_prompt
                    }
                ],
                text_format=TaskVerification
            )
            
            verification = response.output_parsed
            self._add_to_internal_context("llm_assessments", f"Accomplished: {verification.accomplished}, Summary: {verification.summary}")
            return verification
            
        except Exception as e:
            print(f"Error verifying task completion: {e}")
            fallback_verification = TaskVerification(
                accomplished=execution_result['success'],
                summary=f"Verification failed, using execution result: {execution_result['output']}"
            )
            self._add_to_internal_context("llm_assessments", f"Verification error: {str(e)}")
            return fallback_verification
    
    def _get_user_task_confirmation(self, prompt: str) -> tuple[bool, Optional[str]]:
        """Get user confirmation that the task was accomplished."""
        confirmation = input(f"\nWas this step accomplished: '{prompt}'? (y/n): ").strip().lower()
        
        if confirmation in ['y', 'yes']:
            self._add_to_internal_context("user_confirmations", True)
            return True, None
        elif confirmation in ['n', 'no']:
            self._add_to_internal_context("user_confirmations", False)
            feedback = input("What went wrong? ").strip()
            if feedback:
                self._add_to_internal_context("failure_reasons", feedback)
                return False, feedback
            else:
                self._add_to_internal_context("failure_reasons", "User said task not accomplished but provided no specific feedback")
                return False, None
        else:
            print("Please answer 'y' for yes or 'n' for no.")
            return self._get_user_task_confirmation(prompt)
    
    def handle(self, prompt: str, context: str) -> Dict[str, Any]:
        """
        Main handler function with complete AppleScript workflow.
        
        Args:
            prompt: The task to accomplish
            context: Context string from previous steps
        
        Returns:
            Dict containing applescript, prompt, output, and summary
        """
        print(f"\n🍎 AppleScript Handler: {prompt}")
        
        max_attempts = 5  # Prevent infinite loops
        attempt = 0
        
        while attempt < max_attempts:
            attempt += 1
            print(f"\n--- Attempt {attempt} ---")
            
            # Step 1: Generate AppleScript
            script = self._generate_applescript(prompt, context)
            if not script:
                print("❌ Failed to generate AppleScript")
                continue
            
            # Step 2: Get user approval for script (handles regeneration internally)
            approved, approved_script = self._get_user_script_approval(script, prompt, context)
            if not approved:
                print("❌ User rejected script")
                break
            
            # Step 3: Execute the approved script
            execution_result = self._execute_applescript(approved_script)
            
            # Step 4: Get LLM verification
            verification = self._verify_task_completion(prompt, approved_script, execution_result)
            
            # Step 5: Handle task completion logic
            if verification.accomplished:
                # LLM says task accomplished - ask user for confirmation
                user_confirmed, user_feedback = self._get_user_task_confirmation(prompt)
                
                if user_confirmed:
                    # Success! Return the result
                    return {
                        "applescript": approved_script,
                        "prompt": prompt,
                        "output": execution_result['output'],
                        "summary": verification.summary,
                        "handler_type": "applescript"
                    }
                else:
                    # User says task not accomplished - add feedback and retry
                    if user_feedback:
                        print(f"User feedback: {user_feedback}")
                    continue
            else:
                # LLM says task not accomplished - use summary and retry
                print(f"LLM assessment: Task not accomplished - {verification.summary}")
                self._add_to_internal_context("failure_reasons", verification.summary)
                continue
        
        # If we get here, all attempts failed
        print(f"❌ AppleScript handler failed after {max_attempts} attempts")
        return {
            "applescript": "Failed to generate working script",
            "prompt": prompt,
            "output": "Task could not be completed after multiple attempts",
            "summary": f"Failed after {max_attempts} attempts",
            "handler_type": "applescript",
            "error": True
        }

# Global handler instance to maintain state
_handler_instance = None

def handle(prompt: str, context: str) -> Dict[str, Any]:
    """Public interface for the AppleScript handler."""
    global _handler_instance
    if _handler_instance is None:
        _handler_instance = AppleScriptHandler()
    return _handler_instance.handle(prompt, context)

def generateMarkdown(result: Dict[str, Any]) -> str:
    """Generate markdown summary of AppleScript execution."""
    prompt = result.get("prompt", "Unknown task")
    applescript = result.get("applescript", "No script")
    output = result.get("output", "No output")
    summary = result.get("summary", "No summary")
    
    if result.get("error"):
        return f"Prompt: {prompt}. AppleScript execution failed: {output}"
    
    return f"Prompt: {prompt}. The following applescript was run: {applescript} and produced the following output: {output}, and the step was deemed accomplished. The task results were summarized as: {summary}"