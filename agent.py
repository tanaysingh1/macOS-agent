#!/usr/bin/env python3
"""
Agent.py - Intelligent Automation Agent

This agent takes a prompt via command line argument and uses AI APIs to classify,
plan, and execute automation tasks with user oversight.

Core Workflow:
1. Accept prompt via command line argument
2. Use OpenAI Responses API for structured task classification
3. Route to appropriate handler (browser, applescript, automation)
4. Implement full user approval workflow with continuous feedback
5. Execute and verify each step using AI verification
6. Generate comprehensive summary of actions taken

The feedback system works through continuous loops:
- Generate AppleScript using Anthropic API
- Display script to user for approval
- If rejected, collect user feedback and regenerate
- If approved, execute via osascript subprocess
- Verify execution with OpenAI structured output
- Retry up to 3 times per step if verification fails
"""

import argparse
import asyncio
import os
import subprocess
import sys
from typing import List, Dict, Any, Optional
from enum import Enum
import requests
from openai import OpenAI
import anthropic
from pydantic import BaseModel
from stagehand import Stagehand

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class TaskType(str, Enum):
    BROWSER = "browser"
    APPLESCRIPT = "applescript"
    AUTOMATION = "automation"


class TaskClassification(BaseModel):
    taskType: TaskType
    steps: List[str]


class StepVerification(BaseModel):
    success: bool
    feedback: str


class StepExtraction(BaseModel):
    url: str
    prompt: str


class TaskSummary(BaseModel):
    summary: str
    completed_successfully: bool
    total_steps: int
    successful_steps: int


class Agent:
    def __init__(self):
        self.openai_client = OpenAI()
        self.anthropic_client = anthropic.Anthropic()
        self.execution_history = []
        
    def parse_arguments(self) -> str:
        parser = argparse.ArgumentParser(description="Intelligent Automation Agent")
        parser.add_argument("prompt", help="The task prompt to execute")
        args = parser.parse_args()
        return args.prompt
    
    def classify_task(self, prompt: str) -> TaskClassification:
        """Use OpenAI Responses API to classify the task and break it into steps."""
        try:
            response = self.openai_client.responses.parse(
                model="gpt-4o-2024-08-06",
                input=[
                    {
                        "role": "system", 
                        "content": "Analyze the user's request and classify it as either 'browser', 'applescript', or 'automation' based on the task type. Break down the "
                        "task into clear, actionable steps, and write a list of detialed instructions for each step. If something needs to be done in the browser, classify as browser. If something needs to be done with"
                        " files, classify as applescript. If the user wants something done with an app, and its a well known app, especially if its a mac default app, "
                        "classify as applescript. If the user needs you to use a specific app that's not an apple default or not well known, classify as automation; "
                        "this should be used as a last resort. PLEASE NOTE THE FOLLOWING ABOUT APPLESCRIPT REQUESTS: A: it is done via osascript, no need for script"
                        " editor. B: Each step must tell it an app to open, and what to do in that app. You may NEVER ask it to do something in an app on one step and "
                        "ask it to do something else in that same app on the second step; if you need to do two things in one step, classify it as the same step. C: If"
                        " the user's prompt is  something file related, normally all you must do is have one step to do shell commands to execute the task. D: If the instructions"
                        "of the step include instructions to run a command, make sure to include in the step instructions to include applescript to open and activate the "
                        "terminal. WHEN YOU ACTIVATE THE TERMINAL, HAVE IT RUN THE COMMAND IN THE SAME STEP. PLEASE NOTE THE FOLLOWING ABOUT BROWSER REQUESTS: A. Each step must consist of a URL to go to and what to do on that URL( in natural language"
                        ") B. All tasks that need to be completed sequentially on a single page must be done in one step. Don't ever say to do something on a page in one step and then"
                        "try to continue on that page in the next step. Each step should have a unique URL; if you want to do multiple things on a page, include all instructions"
                        "in one step."

                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                text_format=TaskClassification
            )
            return response.output_parsed
        except Exception as e:
            print(f"Error classifying task: {e}")
            sys.exit(1)
    
    def route_to_handler(self, classification: TaskClassification) -> bool:
        """Route the task to the appropriate handler based on taskType."""
        print(f"Task classified as: {classification.taskType}")
        print(f"Steps to execute: {len(classification.steps)}")
        
        if classification.taskType == TaskType.APPLESCRIPT:
            return self.applescript_handler(classification.steps)
        elif classification.taskType == TaskType.BROWSER:
            return self.browser_agent_handler(classification.steps)
        elif classification.taskType == TaskType.AUTOMATION:
            return self.automation_handler(classification.steps)
        else:
            print(f"Unknown task type: {classification.taskType}")
            return False
    
    def browser_agent_handler(self, steps: List[str]) -> bool:
        """Handle browser automation with full user approval workflow using Stagehand."""
        print(f"\n=== Starting Browser Agent Handler ===")
        print(f"Executing {len(steps)} browser steps with user approval workflow\n")
        
        # Use asyncio to run the async browser handler
        return asyncio.run(self._async_browser_handler(steps))
    
    async def _async_browser_handler(self, steps: List[str]) -> bool:
        """Async implementation of browser handler."""
        chrome_process = None
        stagehand = None
        context = ""
        successful_steps = 0
        
        try:
            # Launch Chrome with remote debugging
            chrome_process = self._launch_chrome_debug()
            
            # Initialize Stagehand
            #stagehand = await self._init_stagehand()
            
            for step_num, step in enumerate(steps, 1):
                print(f"--- Step {step_num}/{len(steps)}: {step} ---")
                
                # Extract URL and prompt from step
                extraction = self._extract_url_and_prompt(step, context)
                if not extraction:
                    print(f"❌ Step {step_num} failed: Could not extract URL and prompt")
                    break
                
                # Get user approval
                if not self._get_browser_approval(extraction, step):
                    print(f"❌ Step {step_num} failed: User rejected extraction")
                    break
                
                # Execute the browser step
                result = await self._execute_browser_step( extraction, context)
                
                # Add result to execution history and context
                self.execution_history.append({
                    'step': step,
                    'extraction': {
                        'url': extraction.url,
                        'prompt': extraction.prompt
                    },
                    'result': result,
                    'timestamp': __import__('datetime').datetime.now().isoformat()
                })
                
                if result['success']:
                    successful_steps += 1
                    context += f"\nStep {step_num} completed: {result['output']}"
                    print(f"✅ Step {step_num} completed successfully\n")
                else:
                    print(f"❌ Step {step_num} failed: {result.get('error', 'Unknown error')}\n")
                    break
            
        except Exception as e:
            print(f"💥 Browser handler error: {e}")
        
        finally:
            # Cleanup
            if stagehand:
                try:
                    await stagehand.close()
                    print("  🔧 Stagehand closed")
                except Exception as e:
                    print(f"  Warning: Error closing Stagehand: {e}")
            
            if chrome_process:
                try:
                    chrome_process.terminate()
                    chrome_process.wait(timeout=5)
                    print("  🔧 Chrome process terminated")
                except Exception as e:
                    print(f"  Warning: Error terminating Chrome: {e}")
        
        print(f"=== Browser Agent Handler Complete ===")
        print(f"Successfully completed {successful_steps}/{len(steps)} steps")
        
        return successful_steps == len(steps)
    
    def automation_handler(self, steps: List[str]) -> bool:
        """Placeholder handler for general automation tasks."""
        print("General automation handler not yet implemented")
        print(f"Would execute {len(steps)} automation steps:")
        for i, step in enumerate(steps, 1):
            print(f"  {i}. {step}")
        return False
    
    def applescript_handler(self, steps: List[str]) -> bool:
        """Handle AppleScript automation with full user approval workflow."""
        print(f"\n=== Starting AppleScript Handler ===")
        print(f"Executing {len(steps)} steps with user approval workflow\n: {steps}")
        
        successful_steps = 0
        
        for step_num, step in enumerate(steps, 1):
            print(f"--- Step {step_num}/{len(steps)}: {step} ---")
            
            if self._execute_applescript_step(step, step_num):
                successful_steps += 1
                print(f"✅ Step {step_num} completed successfully\n")
            else:
                print(f"❌ Step {step_num} failed after 3 attempts\n")
                print("🛑 Stopping execution due to continuous errors")
                break
        
        print(f"=== AppleScript Handler Complete ===")
        print(f"Successfully completed {successful_steps}/{len(steps)} steps")
        
        return successful_steps == len(steps)
    
    def _execute_applescript_step(self, step: str, step_num: int) -> bool:
        """Execute a single AppleScript step with retry mechanism."""
        context = f"Step {step_num}: {step}"
        attempted_scripts = []
        
        for attempt in range(1, 4):  # 3 attempts max
            print(f"  Attempt {attempt}/3")
            
            # Generate AppleScript using Anthropic
            script = self._generate_applescript(step, context, attempted_scripts)
            if not script:
                continue
                
            # User approval workflow
            if not self._get_user_approval(script, step):
                continue
                
            # Execute the script
            execution_result = self._execute_script(script)
            attempted_scripts.append({
                'script': script,
                'output': execution_result['output'],
                'success': execution_result['success']
            })
            
            # Verify execution
            verification = self._verify_step_completion(step, script, execution_result)
            
            if verification.success:
                print(f"  ✅ {verification.feedback}")
                return True
            else:
                print(f"  ❌ {verification.feedback}")
                context += f"\n\nPrevious attempt {attempt} failed: {verification.feedback}"
                
        return False
    
    def _generate_applescript(self, step: str, context: str, attempted_scripts: List[Dict]) -> Optional[str]:
        """Generate AppleScript using Anthropic API."""
        try:
            # Build context with previous attempts if any
            context_msg = f"Generate AppleScript to accomplish: {step}\n\nContext: {context}"
            
            if attempted_scripts:
                context_msg += "\n\nPrevious attempts that failed:"
                for i, attempt in enumerate(attempted_scripts, 1):
                    context_msg += f"\n\nAttempt {i}:"
                    context_msg += f"\nScript: {attempt['script']}"
                    context_msg += f"\nOutput: {attempt['output']}"
                    context_msg += f"\nSuccess: {attempt['success']}"
            
            response = self.anthropic_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                messages=[
                    {
                        "role": "user",
                        "content": f"{context_msg}\n\nPlease generate AppleScript code that will accomplish this task. Return only the AppleScript code, no explanations, and NO markdown. Keep in mind that the script MUST be compatible with a macbook."
                    }
                ]
            )
            
            script = response.content[0].text.strip()
            # Remove code block markers if present
            if script.startswith('```'):
                script = '\n'.join(script.split('\n')[1:-1])
            
            return script
            
        except Exception as e:
            print(f"    Error generating AppleScript: {e}")
            return None
    
    def _get_user_approval(self, script: str, step: str) -> bool:
        """Get user approval for the generated AppleScript with feedback loop."""
        while True:
            print(f"\n  Generated AppleScript for: {step}")
            print("  " + "="*50)
            print("  " + script.replace('\n', '\n  '))
            print("  " + "="*50)
            
            approval = input("\n  Approve this script? (y/n): ").strip().lower()
            
            if approval in ['y', 'yes']:
                return True
            elif approval in ['n', 'no']:
                feedback = input("  What's wrong with this script? ").strip()
                if feedback:
                    # Regenerate script with user feedback
                    print(f"  Regenerating script based on feedback: {feedback}")
                    try:
                        response = self.anthropic_client.messages.create(
                            model="claude-sonnet-4-20250514",
                            max_tokens=1000,
                            messages=[
                                {
                                    "role": "user",
                                    "content": f"Generate AppleScript to accomplish: {step}\n\nThe previous script was:\n{script}\n\nUser feedback: {feedback}\n\nPlease generate an improved AppleScript that addresses this feedback. Return only the AppleScript code, no explanations, and NO markdown. Keep in mind that the script MUST be compatible with a macbook."
                                }
                            ]
                        )
                        
                        new_script = response.content[0].text.strip()
                        if new_script.startswith('```'):
                            new_script = '\n'.join(new_script.split('\n')[1:-1])
                        
                        script = new_script
                        continue
                        
                    except Exception as e:
                        print(f"    Error regenerating script: {e}")
                        return False
                else:
                    return False
            else:
                print("  Please answer 'y' for yes or 'n' for no.")
    
    def _execute_script(self, script: str) -> Dict[str, Any]:
        """Execute AppleScript using osascript subprocess."""
        try:
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
            
            print(f"  Script executed with return code: {result.returncode}")
            if execution_result['output']:
                print(f"  Output: {execution_result['output']}")
            
            self.execution_history.append({
                'script': script,
                'result': execution_result,
                'timestamp': __import__('datetime').datetime.now().isoformat()
            })
            
            return execution_result
            
        except subprocess.TimeoutExpired:
            print("  Script execution timed out after 30 seconds")
            return {'success': False, 'output': 'Script execution timed out', 'return_code': -1}
        except Exception as e:
            print(f"  Error executing script: {e}")
            return {'success': False, 'output': str(e), 'return_code': -1}
    
    def _verify_step_completion(self, step: str, script: str, execution_result: Dict[str, Any]) -> StepVerification:
        """Verify if the step was completed successfully using OpenAI."""
        try:
            verification_prompt = f"""
Task: {step}
AppleScript executed: {script}
Execution successful: {execution_result['success']}
Execution output: {execution_result['output']}
Return code: {execution_result['return_code']}

Based on the task, script, and execution results, determine if the step was accomplished successfully.
"""
            
            response = self.openai_client.responses.parse(
                model="gpt-4o-2024-08-06",
                input=[
                    {
                        "role": "system",
                        "content": "You are verifying if an AppleScript execution completed a task successfully. Analyze the task, script, and execution results to determine success and provide helpful feedback."
                    },
                    {
                        "role": "user",
                        "content": verification_prompt
                    }
                ],
                text_format=StepVerification
            )
            
            return response.output_parsed
            
        except Exception as e:
            print(f"    Error verifying step completion: {e}")
            return StepVerification(
                success=execution_result['success'],
                feedback=f"Verification failed, using execution result: {execution_result['output']}"
            )
    
    def generate_final_summary(self, original_prompt: str, successful_steps: int, total_steps: int) -> str:
        """Generate a final summary of the agent's actions using OpenAI."""
        try:
            history_text = "\n\n".join([
                self._format_history_entry(i+1, entry)
                for i, entry in enumerate(self.execution_history)
            ])
            print("HISTORYTEXT:"+ history_text)
            
            summary_prompt = f"""
Original user request: {original_prompt}
Total steps planned: {total_steps}
Successfully completed steps: {successful_steps}

Execution history:
{history_text}

Generate a comprehensive summary of what the agent accomplished, including what worked, what didn't work, and the final outcome.
"""
            
            response = self.openai_client.responses.parse(
                model="gpt-4o-2024-08-06",
                input=[
                    {
                        "role": "system",
                        "content": "Generate a comprehensive summary of the agent's automation session. Explain any data that was collected and the results of every step Be clear about what was accomplished and any issues encountered."
                    },
                    {
                        "role": "user",
                        "content": summary_prompt
                    }
                ],
                text_format=TaskSummary
            )
            
            summary = response.output_parsed
            
            print(f"\n{'='*60}")
            print("FINAL SUMMARY")
            print(f"{'='*60}")
            print(f"Task Status: {'✅ COMPLETED' if summary.completed_successfully else '❌ INCOMPLETE'}")
            print(f"Steps Completed: {summary.successful_steps}/{summary.total_steps}")
            print(f"\n{summary.summary}")
            print(f"{'='*60}")
            
            return summary.summary
            
        except Exception as e:
            fallback_summary = f"Agent completed {successful_steps}/{total_steps} steps for task: {original_prompt}"
            print(f"Error generating summary: {e}")
            print(f"Fallback summary: {fallback_summary}")
            return fallback_summary
    
    def _format_history_entry(self, step_num: int, entry: Dict[str, Any]) -> str:
        """Format execution history entry for both AppleScript and browser steps."""
        if 'script' in entry:
            # AppleScript entry
            return f"Step {step_num} (AppleScript): {entry['script']}\nResult: {entry['result']}\nTimestamp: {entry['timestamp']}"
        elif 'extraction' in entry:
            # Browser entry
            return f"Step {step_num} (Browser): URL={entry['extraction']['url']}, Task={entry['extraction']['prompt']}\nResult: {entry['result']}\nTimestamp: {entry['timestamp']}"
        else:
            # Fallback for unknown entry types
            return f"Step {step_num}: {entry}\nTimestamp: {entry.get('timestamp', 'Unknown')}"
    
    def _launch_chrome_debug(self) -> subprocess.Popen:
        """Launch Chrome with remote debugging enabled."""
        CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        DEBUG_PORT = 9222
        USER_DATA_DIR = "/tmp/chrome-debug-profile"
        try:
            cmd = [
                CHROME_PATH,
                f"--remote-debugging-port={DEBUG_PORT}",
                f"--user-data-dir={USER_DATA_DIR}",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-extensions",
                "--disable-default-apps"
            ]
            
            print("🚀 Launching Chrome with remote debugging...")
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            # Give Chrome a moment to start up
            import time
            time.sleep(3)
            url = f"http://127.0.0.1:{DEBUG_PORT}/json/version"
            r = requests.get(url, timeout=1)
            print( "Status"+  str(r.status_code))
            
            print(f"  Chrome launched with PID: {process.pid}")
            return process
            
        except Exception as e:
            print(f"  Error launching Chrome: {e}")
            raise
    
    def _extract_url_and_prompt(self, step: str, context: str = "", attempted_extractions: List[Dict] = None) -> Optional[StepExtraction]:
        """Extract URL and prompt from a browser step using OpenAI."""
        try:
            context_msg = f"Extract the URL to navigate to and the prompt/task to execute from this browser step: {step}\n\nContext: {context}"
            
            if attempted_extractions:
                context_msg += "\n\nPrevious extraction attempts that were rejected:"
                for i, attempt in enumerate(attempted_extractions, 1):
                    context_msg += f"\n\nAttempt {i}:"
                    context_msg += f"\nURL: {attempt['url']}"
                    context_msg += f"\nPrompt: {attempt['prompt']}"
                    context_msg += f"\nUser feedback: {attempt.get('feedback', 'No feedback')}"
            
            response = self.openai_client.responses.parse(
                model="gpt-4o-2024-08-06",
                input=[
                    {
                        "role": "system",
                        "content": "Extract the URL to navigate to and the specific task/prompt to execute on that page. The URL should be complete and valid. The prompt should be clear instructions for what to do on that page."
                    },
                    {
                        "role": "user",
                        "content": context_msg
                    }
                ],
                text_format=StepExtraction
            )
            
            return response.output_parsed
            
        except Exception as e:
            print(f"    Error extracting URL and prompt: {e}")
            return None
    
    def _get_browser_approval(self, extraction: StepExtraction, step: str) -> bool:
        """Get user approval for the extracted URL and prompt with feedback loop."""
        while True:
            print(f"\n  Extracted from step: {step}")
            print("  " + "="*50)
            print(f"  URL: {extraction.url}")
            print(f"  Task: {extraction.prompt}")
            print("  " + "="*50)
            
            approval = input("\n  Approve this URL and task? (y/n): ").strip().lower()
            
            if approval in ['y', 'yes']:
                return True
            elif approval in ['n', 'no']:
                feedback = input("  What needs to be changed about the URL or task? ").strip()
                if feedback:
                    # Re-extract with user feedback
                    print(f"  Re-extracting based on feedback: {feedback}")
                    attempted_extractions = [{
                        'url': extraction.url,
                        'prompt': extraction.prompt,
                        'feedback': feedback
                    }]
                    
                    new_extraction = self._extract_url_and_prompt(
                        step, 
                        context=f"User feedback: {feedback}",
                        attempted_extractions=attempted_extractions
                    )
                    
                    if new_extraction:
                        extraction = new_extraction
                        continue
                    else:
                        print("  Failed to re-extract. Please try again.")
                        return False
                else:
                    return False
            else:
                print("  Please answer 'y' for yes or 'n' for no.")
    
    async def _init_stagehand(self) -> Stagehand:
        """Initialize Stagehand with CDP connection."""
        try:
            stagehand = Stagehand(
                env="LOCAL",
                local_browser_launch_options={
                    "cdp_url": "http://127.0.0.1:9222"
                }
            )
            
            await stagehand.init()
            print("  ✅ Stagehand initialized successfully")
            return stagehand
            
        except Exception as e:
            print(f"  Error initializing Stagehand: {e}")
            raise
    
    async def _execute_browser_step(self, extraction: StepExtraction, context: str = "") -> Dict[str, Any]:
        """Execute a browser step using Stagehand."""
        try:
            stagehand = Stagehand(
                env="LOCAL",
                local_browser_launch_options={
                    "cdp_url": "http://127.0.0.1:9222"
                }
            )
            
            await stagehand.init()
            print("  ✅ Stagehand initialized successfully")
            # Create Stagehand agent - use keyword arguments
            agent = stagehand.agent(
                provider="anthropic",
                model="claude-sonnet-4-20250514",
                instructions="You are a helpful assistant that can use a web browser.",
                options={
                    "apiKey": os.getenv("ANTHROPIC_API_KEY"),
                }
            )
            
            
            # Get the page from Stagehand
            page = stagehand.page
            
            # Navigate to URL
            print(f"  🌐 Navigating to: {extraction.url}")
            await page.goto(extraction.url)
            
            # Execute the prompt with context
            full_prompt = extraction.prompt
            if context:
                full_prompt = f"Context from previous steps: {context}\n\nCurrent task: {extraction.prompt}"
            
            print(f"  🤖 Executing task: {extraction.prompt}")
            result = await agent.execute(full_prompt)
            
            execution_result = {
                'success': result.completed,
                'url': extraction.url,
                'prompt': extraction.prompt,
                'output': result.message
            }
            
            print(f"  ✅ Task completed successfully")
            if result:
                print(f"  Result: {result}")
            
            return execution_result
            
        except Exception as e:
            print(f"  ❌ Error executing browser step: {e}")
            return {
                'success': False,
                'result': None,
                'url': extraction.url,
                'prompt': extraction.prompt,
                'error': str(e)
            }
    
    def run(self) -> None:
        """Main execution method that orchestrates the entire workflow."""
        try:
            # Parse command line arguments
            prompt = self.parse_arguments()
            print(f"🤖 Agent starting with prompt: {prompt}\n")
            
            # Classify the task using OpenAI
            print("📝 Classifying task and generating steps...")
            classification = self.classify_task(prompt)
            
            # Route to appropriate handler
            success = self.route_to_handler(classification)
            
            # Generate final summary
            successful_steps = sum(1 for entry in self.execution_history if entry['result']['success'])
            total_steps = len(classification.steps)
            
            self.generate_final_summary(prompt, successful_steps, total_steps)
            
            # Exit with appropriate code
            sys.exit(0 if success else 1)
            
        except KeyboardInterrupt:
            print("\n\n🛑 Agent interrupted by user")
            sys.exit(1)
        except Exception as e:
            print(f"\n💥 Fatal error: {e}")
            sys.exit(1)


def main():
    """Entry point for the agent."""
    agent = Agent()
    agent.run()


if __name__ == "__main__":
    main()