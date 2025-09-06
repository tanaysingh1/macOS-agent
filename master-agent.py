#!/usr/bin/env python3
"""
Master Agent 2.0 - Intelligent Automation Agent with Subagent Architecture

This master agent takes a prompt and generates a structured list of steps.
Each step contains a prompt and task classification (browser, applescript, terminal, web_search).
It executes steps sequentially using specialized subagent handlers and maintains context.

Workflow:
1. Accept prompt via command line
2. Generate structured plan with OpenAI
3. Display plan as markdown and request user approval
4. Execute steps sequentially using appropriate subagent handlers
5. Maintain context array and pass context string between handlers
6. Generate final inference summary
"""

import argparse
import sys
import os
from typing import List, Dict, Any, Optional
from enum import Enum
from pathlib import Path
from openai import OpenAI
from pydantic import BaseModel
from dotenv import load_dotenv
from subagents import research, applescript

# Load environment variables
load_dotenv()

class TaskType(str, Enum):
    BROWSER = "browser"
    APPLESCRIPT = "applescript"
    TERMINAL = "terminal"
    WEB_SEARCH = "web_search"

class Step(BaseModel):
    prompt: str
    task_classification: TaskType

class ExecutionPlan(BaseModel):
    steps: List[Step]

class MasterAgent:
    def __init__(self):
        self.openai_client = OpenAI()
        self.context = []
        self.context_string = ""
        
    def parse_arguments(self) -> str:
        parser = argparse.ArgumentParser(description="Master Agent 2.0 - Intelligent Automation")
        parser.add_argument("prompt", help="The task prompt to execute")
        args = parser.parse_args()
        return args.prompt
    
    def generate_plan(self, prompt: str) -> ExecutionPlan:
        """Generate structured execution plan using OpenAI."""
        try:
            response = self.openai_client.responses.parse(
                model="gpt-4o-2024-08-06",
                input=[
                    {
                        "role": "system",
                        "content": (
                            "Generate a structured execution plan for the given prompt. "
                            "Break down the task into clear steps, each with a specific prompt and task classification. "
                            "Task classifications are: 'web_search' (for research/information gathering), "
                            "'applescript' (app control), "
                            "'browser' (for web interactions), 'terminal' (for command line operations such as file system operations). "
                            "If the user asks to find specific information, use a web_search step, with a prompt thats ideally a one line question"
                            "asking for information."
                            "If the user asks for something to be done with a specific app, use applescript and specify in natural language what"
                            "apps to use and what to do on each app. IMPORTANT: please note that applescript steps should never be one after"
                            "the other. That is to say, unless absolutely necessary, if you need to do two different automations in a row, please"
                            "put them in one applescript step. IF the user EXPLICITLY asks for multiple steps, as in they actually label as step 1, step 2, etc, then do that, but otherwise, try "
                            "to not have multiple in a row. You can have multiple applescript steps in the whole step list, but never one after another. So you may never"
                            "generate output like Step 1: applescript, step 2: applescript. Remember, you can use multiple apps in the same applescript step."
                            "If the user EXPLICTLY ASKS for an action on a browser, classify as a browser step. If the user is specifically asking"
                            "for information, web_search is almost always more appropriate. Finally, if the user asks for anything file system related or"
                            "command line related, classify as termianl. like with applescript, try not to have multiple terminal steps in a row;"
                            "iof multiple things need to be done with the terminal ina row, put them all in one step. "
                        )
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                text_format=ExecutionPlan
            )
            return response.output_parsed
        except Exception as e:
            print(f"Error generating plan: {e}")
            sys.exit(1)
    
    def display_plan_markdown(self, plan: ExecutionPlan, original_prompt: str) -> None:
        """Display the execution plan as markdown."""
        print("\n" + "="*60)
        print("EXECUTION PLAN")
        print("="*60)
        print(f"**Original Prompt:** {original_prompt}\n")
        print(f"**Total Steps:** {len(plan.steps)}\n")
        
        for i, step in enumerate(plan.steps, 1):
            print(f"### Step {i}: {step.task_classification.value.upper()}")
            print(f"**Task:** {step.prompt}\n")
        
        print("="*60)
    
    def get_user_approval(self, plan: ExecutionPlan, original_prompt: str) -> ExecutionPlan:
        """Get user approval for the plan with feedback loop."""
        while True:
            self.display_plan_markdown(plan, original_prompt)
            
            approval = input("\nApprove this execution plan? (y/n): ").strip().lower()
            
            if approval in ['y', 'yes']:
                return plan
            elif approval in ['n', 'no']:
                feedback = input("What's wrong with the plan? ").strip()
                if feedback:
                    print(f"Regenerating plan based on feedback: {feedback}")
                    
                    # Regenerate plan with user feedback
                    try:
                        response = self.openai_client.responses.parse(
                            model="gpt-4o-2024-08-06",
                            input=[
                                {
                                    "role": "system",
                                    "content": (
                                        "Generate a revised execution plan based on the original prompt and user feedback. "
                                        "Break down the task into clear steps, each with a specific prompt and task classification. "
                                        "Task classifications are: 'web_search' (for research/information gathering), "
                                        "'applescript' (for Mac automation, file operations, app control), "
                                        "'browser' (for web interactions), 'terminal' (for command line operations). "
                                        "Each step should be atomic and actionable."
                                    )
                                },
                                {
                                    "role": "user",
                                    "content": f"Original prompt: {original_prompt}\n\nPrevious plan had issues. User feedback: {feedback}\n\nPlease generate an improved plan."
                                }
                            ],
                            text_format=ExecutionPlan
                        )
                        plan = response.output_parsed
                        continue
                    except Exception as e:
                        print(f"Error regenerating plan: {e}")
                        return plan
                else:
                    sys.exit(1)
            else:
                print("Please answer 'y' for yes or 'n' for no.")
    
    def get_handler(self, task_type: TaskType):
        """Get the appropriate subagent handler."""
        handler_map = {
            TaskType.WEB_SEARCH: research,
            TaskType.APPLESCRIPT: applescript
        }
        
        return handler_map.get(task_type)
    
    def execute_steps(self, plan: ExecutionPlan) -> None:
        """Execute all steps in the plan sequentially."""
        print(f"\n{'='*60}")
        print("EXECUTING PLAN")
        print(f"{'='*60}")
        
        for i, step in enumerate(plan.steps, 1):
            print(f"\n--- Step {i}/{len(plan.steps)}: {step.task_classification.value.upper()} ---")
            print(f"Task: {step.prompt}")
            
            # Get the appropriate handler
            handler_module = self.get_handler(step.task_classification)
            
            if handler_module is None:
                print(f"❌ Step {i} failed: Handler for {step.task_classification} not available")
                break
            
            try:
                # Execute the step
                result = handler_module.handle(step.prompt, self.context_string)
                
                # Add result to context array
                self.context.append(result)
                
                # Generate markdown and add to context string
                markdown = handler_module.generateMarkdown(result)
                self.context_string += f"\n\n{markdown}"
                
                print(f"✅ Step {i} completed successfully")
                
            except Exception as e:
                print(f"❌ Step {i} failed with error: {e}")
                break
    
    def generate_final_inference(self, original_prompt: str) -> None:
        """Generate final inference based on all executed steps."""
        try:
            # Generate LLM summary of the workflow
            response = self.openai_client.responses.create(
                model="gpt-5",
                input=[
                    {
                        "role": "system",
                        "content": "Generate a comprehensive summary of the agent workflow. Highlight key information collected, actions taken, and overall outcomes. Be clear and concise about what was accomplished."
                    },
                    {
                        "role": "user",
                        "content": f"Original request: {original_prompt}\n\nWorkflow context:\n{self.context_string}\n\nPlease summarize what the agent accomplished, highlighting information collected and actions taken."
                    }
                ]
            )
            
            summary = response.output_text
            
            print(f"\n{'='*60}")
            print("FINAL INFERENCE")
            print(f"{'='*60}")
            print(f"**Original Request:** {original_prompt}\n")
            print("**Agent Summary:**")
            print(summary)
            print(f"\n{'='*60}")
            
        except Exception as e:
            print(e)
    
    def run(self) -> None:
        """Main execution method."""
        try:
            # Parse command line arguments
            prompt = self.parse_arguments()
            print(f"🤖 Master Agent 2.0 starting with prompt: {prompt}")
            
            # Generate execution plan
            print("\n📝 Generating execution plan...")
            plan = self.generate_plan(prompt)
            
            # Get user approval for the plan
            approved_plan = self.get_user_approval(plan, prompt)
            
            # Execute the approved plan
            self.execute_steps(approved_plan)
            
            # Generate final inference
            self.generate_final_inference(prompt)
            
            print("\n🎉 Master Agent execution complete!")
            
        except KeyboardInterrupt:
            print("\n\n🛑 Master Agent interrupted by user")
            sys.exit(1)
        except Exception as e:
            print(f"\n💥 Fatal error: {e}")
            sys.exit(1)

def main():
    """Entry point for the master agent."""
    agent = MasterAgent()
    agent.run()

if __name__ == "__main__":
    main()