"""
J.A.R.V.I.S. — LangChain Agent
Uses Google Gemini as the LLM backbone with a ReAct agent loop.
"""

import logging
from typing import List, Optional

try:
    from langchain.agents import AgentExecutor, create_react_agent
except ImportError:
    from langchain_classic.agents import AgentExecutor, create_react_agent

try:
    from langchain_core.tools import Tool
except ImportError:
    from langchain.tools import Tool
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
import os

logger = logging.getLogger('jarvis.agent')

# ReAct prompt template — guides the model through tool use
REACT_TEMPLATE = """{system_prompt}

{memory_context}

You have access to the following tools:

{tools}

IMPORTANT — You MUST use this exact format:

Question: the input question you must answer
Thought: think about what to do
Action: the action to take, must be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat multiple times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

If no tools are needed, go straight to Final Answer.

Begin!

Question: {input}
Thought: {agent_scratchpad}"""


class JarvisAgent:
    """
    Autonomous ReAct agent powered by Gemini + LangChain.
    Selects and calls tools based on user intent.
    """

    def __init__(
        self,
        api_key:       str,
        model_name:    str,
        tools:         List[Tool],
        system_prompt: str,
        temperature:   float = 0.4,
        max_iterations: int  = 8,
    ):
        self.system_prompt  = system_prompt
        self.memory_context = ''

        logger.info(f'Initialising agent — model: {model_name}')

        # Set env var so langchain-google-genai picks up the key
        os.environ['GOOGLE_API_KEY'] = api_key

        # ── LLM ────────────────────────────────────────────────
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=temperature,
        )

        # ── Prompt ─────────────────────────────────────────────
        self.prompt = PromptTemplate.from_template(REACT_TEMPLATE)

        # ── Agent & Executor ───────────────────────────────────
        agent = create_react_agent(
            llm=self.llm,
            tools=tools,
            prompt=self.prompt,
        )
        self.executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True,
            max_iterations=max_iterations,
            handle_parsing_errors=True,
            return_intermediate_steps=True,
        )

        logger.info('Agent executor ready.')

    def set_memory_context(self, context: str) -> None:
        """Inject memory context (called before each run)."""
        self.memory_context = context

    def run(self, user_input: str) -> str:
        """
        Process a user command through the ReAct agent loop.
        Returns the final text response.
        """
        logger.info(f'Agent input: "{user_input}"')
        try:
            result = self.executor.invoke({
                'input':          user_input,
                'system_prompt':  self.system_prompt,
                'memory_context': self.memory_context or '',
            })
            output = result.get('output', '').strip()
            logger.info(f'Agent output: "{output[:100]}"')
            return output if output else "I'm sorry, Sir — I was unable to produce a response."

        except Exception as e:
            logger.error(f'Agent error: {e}', exc_info=True)
            return (
                f"I encountered an anomaly, Sir: {str(e)[:200]}. "
                "Running diagnostics. Please try again."
            )
