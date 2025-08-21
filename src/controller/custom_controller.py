# import pdb  # Unused
# import pyperclip  # Unused
from typing import Optional, Type, Callable, Dict, Any, Union, Awaitable, TypeVar
from pydantic import BaseModel
from browser_use.agent.views import ActionResult
from browser_use.browser import BrowserSession
from browser_use.controller.service import Controller
from browser_use.controller.registry.service import RegisteredAction
# Removed unused imports: DoneAction, Registry, MainContentExtractor, and view classes
import logging
import inspect
# import asyncio  # Unused
# import os  # Unused
from langchain_core.language_models.chat_models import BaseChatModel
from browser_use.agent.views import ActionModel, ActionResult

from src.utils.mcp_client import create_tool_param_model, setup_mcp_client_and_tools

from browser_use.utils import time_execution_sync

logger = logging.getLogger(__name__)

Context = TypeVar('Context')


class CustomController(Controller):
    def __init__(self, exclude_actions: list[str] = [],
                 output_model: Optional[Type[BaseModel]] = None,
                 ask_assistant_callback: Optional[Union[Callable[[str, BrowserSession], Dict[str, Any]], Callable[
                     [str, BrowserSession], Awaitable[Dict[str, Any]]]]] = None,
                 ):
        super().__init__(exclude_actions=exclude_actions, output_model=output_model)
        self._register_custom_actions()
        self.ask_assistant_callback = ask_assistant_callback
        self.mcp_client = None
        self.mcp_server_config = None

    def _register_custom_actions(self):
        """Register all custom browser actions"""

        @self.registry.action(
            "When executing tasks, prioritize autonomous completion. However, if you encounter a definitive blocker "
            "that prevents you from proceeding independently – such as needing credentials you don't possess, "
            "requiring subjective human judgment, needing a physical action performed, encountering complex CAPTCHAs, "
            "or facing limitations in your capabilities – you must request human assistance."
        )
        async def ask_for_assistant(query: str, browser_session: BrowserSession):
            if self.ask_assistant_callback:
                if inspect.iscoroutinefunction(self.ask_assistant_callback):
                    user_response = await self.ask_assistant_callback(query, browser_session)
                else:
                    user_response = self.ask_assistant_callback(query, browser_session)
                msg = f"AI ask: {query}. User response: {user_response['response']}"
                logger.info(msg)
                return ActionResult(extracted_content=msg, include_in_memory=True)
            else:
                return ActionResult(extracted_content="Human cannot help you. Please try another way.",
                                    include_in_memory=True)

        # TODO: Update upload_file action for browser_use 0.6.0 API
        # The old implementation used methods that don't exist in the new version
        # Commenting out for now to avoid schema generation errors
        
        # @self.registry.action(
        #     'Upload file to interactive element with file path ',
        # )
        # async def upload_file(index: int, path: str, browser_session: BrowserSession, available_file_paths: list[str]):
        #     # This needs to be reimplemented using browser_use 0.6.0 API
        #     return ActionResult(error='File upload not yet implemented for browser_use 0.6.0')

    @time_execution_sync('--act')
    async def act(
            self,
            action: ActionModel,
            browser_session: BrowserSession,
            #
            page_extraction_llm: Optional[BaseChatModel] = None,
            sensitive_data: Optional[Dict[str, str]] = None,
            available_file_paths: Optional[list[str]] = None,
            file_system: Optional[Any] = None,  # Added for compatibility with 0.6.0
            #
            context: Context | None = None,
    ) -> ActionResult:
        """Execute an action - handle MCP tools specially, delegate others to parent"""
        
        # Check if this is an MCP tool
        for action_name, params in action.model_dump(exclude_unset=True).items():
            if params is not None and action_name.startswith("mcp"):
                # Handle MCP tool specially
                logger.debug(f"Invoke MCP tool: {action_name}")
                mcp_tool = self.registry.registry.actions.get(action_name).function
                result = await mcp_tool.ainvoke(params)
                
                if isinstance(result, str):
                    return ActionResult(extracted_content=result)
                elif isinstance(result, ActionResult):
                    return result
                elif result is None:
                    return ActionResult()
                else:
                    raise ValueError(f'Invalid action result type: {type(result)} of {result}')
        
        # For non-MCP actions, delegate to parent class
        return await super().act(
            action=action,
            browser_session=browser_session,
            page_extraction_llm=page_extraction_llm,
            sensitive_data=sensitive_data,
            available_file_paths=available_file_paths,
            file_system=file_system,
            context=context,
        )

    async def setup_mcp_client(self, mcp_server_config: Optional[Dict[str, Any]] = None):
        self.mcp_server_config = mcp_server_config
        if self.mcp_server_config:
            self.mcp_client = await setup_mcp_client_and_tools(self.mcp_server_config)
            self.register_mcp_tools()

    def register_mcp_tools(self):
        """
        Register the MCP tools used by this controller.
        """
        if self.mcp_client:
            for server_name in self.mcp_client.server_name_to_tools:
                for tool in self.mcp_client.server_name_to_tools[server_name]:
                    tool_name = f"mcp.{server_name}.{tool.name}"
                    self.registry.registry.actions[tool_name] = RegisteredAction(
                        name=tool_name,
                        description=tool.description,
                        function=tool,
                        param_model=create_tool_param_model(tool),
                    )
                    logger.info(f"Add mcp tool: {tool_name}")
                logger.debug(
                    f"Registered {len(self.mcp_client.server_name_to_tools[server_name])} mcp tools for {server_name}")
        else:
            logger.warning(f"MCP client not started.")

    async def close_mcp_client(self):
        if self.mcp_client:
            await self.mcp_client.__aexit__(None, None, None)
