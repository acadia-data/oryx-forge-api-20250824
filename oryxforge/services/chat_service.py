"""Chat Service for interactive data analysis conversations."""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any, Literal
from jinja2 import Template
from loguru import logger
from pydantic import BaseModel, Field

# Handle tomllib for Python 3.11+ or tomli for older versions
if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib
    except ImportError:
        raise ImportError("tomli package is required for Python < 3.11. Install it with: pip install tomli")

from .utils import init_supabase_client
from .project_service import ProjectService
from ..agents.claude import ClaudeAgent


# Pydantic models for intent classification structured output
class InputReference(BaseModel):
    """Input data source reference."""
    dataset: str = Field(description="Dataset name_python")
    sheet: str = Field(description="Sheet name_python")


class TargetReference(BaseModel):
    """Output target reference."""
    dataset: str = Field(description="Dataset name_python")
    sheet: str = Field(description="Sheet name_python")
    is_new: bool = Field(description="Whether this is a new sheet")


class IntentClassificationResponse(BaseModel):
    """Structured response for intent classification."""
    action: Literal["new", "edit"] = Field(description="Whether to create new or edit existing")
    inputs: List[InputReference] = Field(default_factory=list, description="Input data sources")
    targets: List[TargetReference] = Field(default_factory=list, description="Output targets - must have exactly one")
    confidence: Literal["high", "medium", "low"] = Field(description="Classification confidence")


class ChatService:
    """
    Service class for managing interactive chat sessions with AI data analysis.

    Handles intent classification, chat history, and orchestrates Claude agent interactions.
    """

    def __init__(self, user_id: str, project_id: str):
        """
        Initialize Chat Service.

        Args:
            user_id: User ID
            project_id: Project ID (also used as session_id)
        """
        self.user_id = user_id
        self.project_id = project_id
        self.session_id = project_id  # session_id = project_id per requirements

        # Initialize clients and services
        self.supabase_client = init_supabase_client()
        self.project_service = ProjectService(project_id=project_id, user_id=user_id)

        # Load prompt templates
        self.templates = self._load_templates()

        # Initialize OpenAI intent classifier
        self.intent_classifier = self._init_intent_classifier()

        logger.debug(f"ChatService initialized for user {user_id}, project {project_id}")

    def _load_templates(self) -> Dict[str, str]:
        """
        Load prompt templates from TOML file.

        Returns:
            Dict containing template strings
        """
        template_path = Path(__file__).parent.parent / "prompts" / "templates.toml"

        with open(template_path, 'rb') as f:
            templates = tomllib.load(f)

        return templates

    def _init_intent_classifier(self):
        """
        Initialize OpenAI LLM with structured output for intent classification.

        Returns:
            LangChain LLM configured with IntentClassificationResponse structured output
        """
        import adtiam
        from langchain_openai import ChatOpenAI

        adtiam.load_creds('adt-llm')
        openai_api_key = adtiam.creds['llm']['openai']

        llm = ChatOpenAI(
            model="gpt-5-nano",
            api_key=openai_api_key
        )

        return llm.with_structured_output(IntentClassificationResponse)

    def _get_chat_history(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get recent chat messages for context.

        Args:
            limit: Maximum number of messages to retrieve

        Returns:
            List of message dicts in chronological order (oldest first)
        """
        try:
            response = (
                self.supabase_client.table("chat_messages")
                .select("id, role, content, content_summary, created_at")
                .eq("session_id", self.session_id)
                .eq("user_owner", self.user_id)
                .in_("role", ["user", "agent"])
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )

            # Reverse to get chronological order (oldest first)
            messages = list(reversed(response.data))
            logger.debug(f"Retrieved {len(messages)} chat history messages")
            return messages

        except Exception as e:
            logger.warning(f"Failed to retrieve chat history: {str(e)}")
            return []

    def _summarize_user_message(self, user_msg: str, previous_agent_msg: Optional[str] = None) -> str:
        """
        Summarize user message using intent summary prompt.

        Args:
            user_msg: Current user message
            previous_agent_msg: Previous agent message content (if any)

        Returns:
            Summary string
        """
        try:
            template_str = self.templates['intent']['prompt_summary_user']
            template = Template(template_str)

            prompt = template.render(
                user_message=user_msg,
                previous_agent_message=previous_agent_msg or ""
            )

            # Call Claude for summarization (use smaller/faster model if available)
            result = ClaudeAgent.query_run(
                query_text=prompt,
                verbose=False
            )

            return result.result.strip()

        except Exception as e:
            logger.warning(f"Failed to summarize user message: {str(e)}")
            # Fallback to truncated message
            return user_msg[:200] + "..." if len(user_msg) > 200 else user_msg

    def _summarize_agent_message(self, user_msg: str, agent_msg: str) -> str:
        """
        Summarize agent message using agent summary prompt.

        Args:
            user_msg: Current user message
            agent_msg: Current agent response

        Returns:
            Summary string
        """
        try:
            template_str = self.templates['intent']['prompt_summary_agent']
            template = Template(template_str)

            prompt = template.render(
                user_message=user_msg,
                agent_message=agent_msg
            )

            # Call Claude for summarization
            result = ClaudeAgent.query_run(
                query_text=prompt,
                verbose=False
            )

            return result.result.strip()

        except Exception as e:
            logger.warning(f"Failed to summarize agent message: {str(e)}")
            # Fallback to truncated message
            return agent_msg[:200] + "..." if len(agent_msg) > 200 else agent_msg

    def intent(self, message_user: str, mode: str, ds_active: Optional[str] = None,
               sheet_active: Optional[str] = None, chat_history: List[Dict] = None) -> Dict[str, Any]:
        """
        Classify user intent and extract inputs/targets.

        Args:
            message_user: User's message
            mode: Current mode (explore, edit, plan)
            ds_active: Active dataset ID (optional)
            sheet_active: Active sheet ID (optional)
            chat_history: Recent chat history (optional)

        Returns:
            Dict with keys: action, inputs, targets, confidence

        Raises:
            ValueError: If multiple targets detected or other validation errors
        """
        try:
            # Get available datasets and sheets
            available_datasets = self.project_service.ds_list()
            available_sheets = self.project_service.sheet_list()

            # Add dataset names to sheets for display
            dataset_map = {ds['id']: ds['name'] for ds in available_datasets}
            dataset_name_python_map = {ds['id']: ds['name_python'] for ds in available_datasets}
            for sheet in available_sheets:
                sheet['dataset_name'] = dataset_map.get(sheet['dataset_id'], 'Unknown')
                sheet['dataset_name_python'] = dataset_name_python_map.get(sheet['dataset_id'], 'unknown')

            # Get active dataset/sheet details if provided
            ds_active_obj = None
            sheet_active_obj = None
            if ds_active:
                try:
                    ds_active_obj = self.project_service.ds_get(id=ds_active)
                except ValueError:
                    pass
            if sheet_active:
                try:
                    sheet_active_obj = self.project_service.sheet_get(id=sheet_active)
                except ValueError:
                    pass

            # Prepare chat history summary
            chat_history_summary = []
            if chat_history:
                for msg in chat_history:
                    if msg.get('content_summary'):
                        chat_history_summary.append({
                            'role': msg['role'],
                            'content_summary': msg['content_summary']
                        })

            # Render intent classification prompt
            template_str = self.templates['intent']['prompt_classification']
            template = Template(template_str)

            prompt = template.render(
                message_user=message_user,
                mode=mode,
                ds_active_name=ds_active_obj['name'] if ds_active_obj else None,
                ds_active_name_python=ds_active_obj['name_python'] if ds_active_obj else None,
                sheet_active_name=sheet_active_obj['name'] if sheet_active_obj else None,
                sheet_active_name_python=sheet_active_obj['name_python'] if sheet_active_obj else None,
                available_datasets=available_datasets,
                available_sheets=available_sheets,
                chat_history_summary=chat_history_summary
            )

            # Call OpenAI for intent classification using structured output
            from langchain_core.prompts import ChatPromptTemplate

            chat_prompt = ChatPromptTemplate.from_messages([
                ("system", "You are a data analysis intent classifier."),
                ("user", "{prompt}")
            ])

            chain = chat_prompt | self.intent_classifier
            logger.info("Calling OpenAI for intent classification")
            pydantic_result = chain.invoke({"prompt": prompt})

            # Debug: log the structured output
            logger.debug(f"OpenAI returned: action={pydantic_result.action}, inputs={len(pydantic_result.inputs)}, targets={len(pydantic_result.targets)}, confidence={pydantic_result.confidence}")

            # Convert Pydantic model to dict
            intent_result = {
                "action": pydantic_result.action,
                "inputs": [inp.model_dump() for inp in pydantic_result.inputs],
                "targets": [target.model_dump() for target in pydantic_result.targets],
                "confidence": pydantic_result.confidence
            }

            # Validate single target
            if len(intent_result.get('targets', [])) > 1:
                raise ValueError(
                    f"Multiple output targets detected: {intent_result['targets']}. "
                    "Please specify only one output dataset/sheet where results should be saved."
                )

            if len(intent_result.get('targets', [])) == 0:
                raise ValueError(
                    "No output target specified. Please clarify where the analysis results should be saved."
                )

            logger.success(f"Intent classified: {intent_result['action']} with {len(intent_result.get('inputs', []))} inputs")
            return intent_result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse intent classification JSON: {str(e)}")
            raise ValueError(f"Failed to understand request. Please rephrase your question. Error: {str(e)}")
        except Exception as e:
            if isinstance(e, ValueError):
                raise
            logger.error(f"Intent classification failed: {str(e)}")
            raise ValueError(f"Failed to classify intent: {str(e)}")

    def chat(self, message_user: str, mode: str, ds_active: Optional[str] = None,
             sheet_active: Optional[str] = None) -> Dict[str, Any]:
        """
        Process a chat message and generate response.

        Args:
            message_user: User's message
            mode: Current mode (explore, edit, plan)
            ds_active: Active dataset ID (optional)
            sheet_active: Active sheet ID (optional)

        Returns:
            Dict with keys:
                - message: Agent response text
                - target_dataset: Target dataset name_python
                - target_sheet: Target sheet name_python
                - cost_usd: Cost of operation
                - duration_ms: Duration of operation
        """
        logger.info(f"Processing chat message in {mode} mode")

        try:
            # Step 1: Get chat history
            chat_history = self._get_chat_history(limit=5)

            # Step 2: Get available datasets and sheets
            available_datasets = self.project_service.ds_list()
            available_sheets = self.project_service.sheet_list()

            # Step 3: Intent classification
            intent_result = self.intent(
                message_user=message_user,
                mode=mode,
                ds_active=ds_active,
                sheet_active=sheet_active,
                chat_history=chat_history
            )

            # Step 4: Validate and resolve inputs
            resolved_inputs = []
            for inp in intent_result.get('inputs', []):
                try:
                    ds = self.project_service.ds_get(name_python=inp['dataset'])
                    sheet = self.project_service.sheet_get(
                        dataset_id=ds['id'],
                        name_python=inp['sheet']
                    )
                    resolved_inputs.append({
                        'dataset': ds['name_python'],
                        'sheet': sheet['name_python']
                    })
                except ValueError as e:
                    raise ValueError(
                        f"Input data not found: {inp['dataset']}.{inp['sheet']}. "
                        f"Please check that the dataset and sheet exist. Error: {str(e)}"
                    )

            # Step 5: Create or get target dataset and sheet
            target = intent_result['targets'][0]

            if target['is_new']:
                # Create new sheet
                logger.info(f"Creating new target: {target['dataset']}.{target['sheet']}")
                target_ds = self.project_service.ds_create_get(name=target['dataset'])
                target_sheet = self.project_service.sheet_create(
                    dataset_id=target_ds['id'],
                    name=target['sheet']
                )
            else:
                # Get existing sheet
                try:
                    target_ds = self.project_service.ds_get(name_python=target['dataset'])
                    target_sheet = self.project_service.sheet_get(
                        dataset_id=target_ds['id'],
                        name_python=target['sheet']
                    )
                except ValueError as e:
                    raise ValueError(
                        f"Target data not found: {target['dataset']}.{target['sheet']}. "
                        f"If you're creating new analysis, I detected this as an edit. "
                        f"Please clarify if you want to edit existing data or create new analysis. Error: {str(e)}"
                    )

            # Step 6: Render Claude prompt
            template_str = self.templates['Chat']['prompt']
            template = Template(template_str)

            prompt = template.render(
                message_user=message_user,
                chat_history=chat_history,
                inputs=resolved_inputs,
                target_dataset=target_ds['name_python'],
                target_sheet=target_sheet['name_python']
            )

            # Step 7: Call Claude
            logger.info("Calling Claude agent for data analysis")
            result = ClaudeAgent.query_run(
                query_text=prompt,
                verbose=True
            )

            message_agent = result.result

            # Step 8: Summarize messages
            # Get previous agent message for user summary context
            previous_agent_msg = None
            if chat_history:
                for msg in reversed(chat_history):
                    if msg['role'] == 'agent':
                        previous_agent_msg = msg['content']
                        break

            user_summary = self._summarize_user_message(message_user, previous_agent_msg)
            agent_summary = self._summarize_agent_message(message_user, message_agent)

            # Step 9: Save user message to database (single insert with content and summary)
            user_metadata = {
                "mode": mode,
                "ds_active": ds_active,
                "sheet_active": sheet_active,
                "intent": {
                    "action": intent_result['action'],
                    "inputs": intent_result.get('inputs', []),
                    "targets": intent_result.get('targets', []),
                    "confidence": intent_result.get('confidence', 'medium')
                }
            }

            user_msg_response = (
                self.supabase_client.table("chat_messages")
                .insert({
                    "user_owner": self.user_id,
                    "project_id": self.project_id,
                    "session_id": self.session_id,
                    "role": "user",
                    "content": message_user,
                    "content_summary": user_summary,
                    "metadata": user_metadata
                })
                .execute()
            )

            user_msg_id = user_msg_response.data[0]['id']
            logger.success(f"Saved user message: {user_msg_id}")

            # Step 10: Save agent message to database (single insert with content and summary)
            agent_metadata = {
                "mode": mode,
                "cost_usd": result.total_cost_usd,
                "duration_ms": result.duration_ms,
                "target": {
                    "dataset": target_ds['name_python'],
                    "sheet": target_sheet['name_python']
                }
            }

            agent_msg_response = (
                self.supabase_client.table("chat_messages")
                .insert({
                    "user_owner": self.user_id,
                    "project_id": self.project_id,
                    "session_id": self.session_id,
                    "role": "agent",
                    "content": message_agent,
                    "content_summary": agent_summary,
                    "metadata": agent_metadata
                })
                .execute()
            )

            agent_msg_id = agent_msg_response.data[0]['id']
            logger.success(f"Saved agent message: {agent_msg_id}")

            # Step 11: Return result
            return {
                "message": message_agent,
                "target_dataset": target_ds['name_python'],
                "target_sheet": target_sheet['name_python'],
                "cost_usd": result.total_cost_usd,
                "duration_ms": result.duration_ms
            }

        except ValueError as e:
            # User-friendly validation errors
            logger.warning(f"Chat validation error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Chat processing failed: {str(e)}")
            raise ValueError(f"Failed to process chat message: {str(e)}")
