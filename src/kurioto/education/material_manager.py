"""
Educational Material Manager

Manages parent-uploaded educational materials using Gemini File Search API.
Handles textbooks, homework assignments, and study guides with metadata
for filtering by subject, grade level, and material type.
"""

import asyncio
from pathlib import Path
from typing import Any

import structlog
from google import genai
from google.genai import types

logger = structlog.get_logger()


class EducationalMaterialManager:
    """
    Manages educational materials using Gemini File Search.

    Each child has an isolated File Search store containing their
    parent-uploaded textbooks, homework, and study materials.
    """

    def __init__(self, child_id: str, client: genai.Client):
        """
        Initialize material manager for a specific child.

        Args:
            child_id: Unique identifier for the child
            client: Initialized Gemini client
        """
        self.child_id = child_id
        self.client = client
        self.store_name = f"child_{child_id}_education"
        self.file_search_store: types.FileSearchStore | None = None

    async def initialize_store(self) -> types.FileSearchStore:
        """
        Create or retrieve child's File Search store.

        Returns:
            FileSearchStore instance for this child

        Raises:
            RuntimeError: If store creation or retrieval fails
        """
        # Try to get existing store first
        try:
            existing_stores = list(self.client.file_search_stores.list())
            for store in existing_stores:
                if store.display_name == self.store_name:
                    self.file_search_store = store
                    logger.info(
                        "retrieved_existing_file_search_store",
                        child_id=self.child_id,
                        store_name=self.store_name,
                    )
                    # Type assertion: we know store is valid here
                    assert self.file_search_store is not None
                    return self.file_search_store
        except Exception as e:
            logger.warning("error_listing_stores", error=str(e), child_id=self.child_id)

        # Create new store if not found
        store = self.client.file_search_stores.create(
            config={"display_name": self.store_name}
        )

        if store is None:
            raise RuntimeError(
                f"Failed to create File Search store for child {self.child_id}"
            )

        self.file_search_store = store

        logger.info(
            "created_new_file_search_store",
            child_id=self.child_id,
            store_name=self.store_name,
            store_id=store.name,
        )

        return store

    async def upload_textbook(
        self,
        file_path: Path,
        subject: str,
        grade_level: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Upload textbook PDF to File Search store with metadata.

        Args:
            file_path: Path to textbook PDF file
            subject: Subject (math, science, english, history, etc.)
            grade_level: Grade level (K, 1-12)
            metadata: Optional additional metadata

        Returns:
            Operation name for tracking upload status

        Example:
            >>> manager = EducationalMaterialManager("child_123", client)
            >>> await manager.initialize_store()
            >>> operation = await manager.upload_textbook(
            ...     Path("math_grade_3.pdf"),
            ...     subject="math",
            ...     grade_level="3"
            ... )
        """
        if not self.file_search_store:
            raise ValueError(
                "File Search store not initialized. Call initialize_store() first."
            )

        # Build metadata for filtering
        custom_metadata = [
            {"key": "type", "string_value": "textbook"},
            {"key": "subject", "string_value": subject.lower()},
            {"key": "grade_level", "string_value": str(grade_level)},
            {"key": "child_id", "string_value": self.child_id},
        ]

        # Add optional metadata
        if metadata:
            for key, value in metadata.items():
                if isinstance(value, (int, float)):
                    custom_metadata.append({"key": key, "numeric_value": float(value)})  # type: ignore[dict-item]
                else:
                    custom_metadata.append({"key": key, "string_value": str(value)})

        logger.info(
            "uploading_textbook",
            child_id=self.child_id,
            file_name=file_path.name,
            subject=subject,
            grade_level=grade_level,
        )

        # Upload and import to File Search store
        operation = self.client.file_search_stores.upload_to_file_search_store(
            file=str(file_path),
            file_search_store_name=self.file_search_store.name,
            config={
                "display_name": file_path.name,
                "custom_metadata": custom_metadata,
                "chunking_config": {
                    "white_space_config": {
                        "max_tokens_per_chunk": 300,  # Optimal for educational content
                        "max_overlap_tokens": 50,  # Preserve context across chunks
                    }
                },
            },
        )

        # Wait for processing to complete
        while not operation.done:
            await asyncio.sleep(2)
            operation = self.client.operations.get(operation)

        logger.info(
            "uploaded_textbook",
            child_id=self.child_id,
            file_name=file_path.name,
            subject=subject,
            grade_level=grade_level,
            operation_name=operation.name,
        )

        return operation.name

    async def upload_homework(
        self,
        file_path: Path,
        subject: str,
        assignment_name: str,
        due_date: str | None = None,
    ) -> str:
        """
        Upload homework assignment (PDF or image).

        Args:
            file_path: Path to homework file
            subject: Subject area
            assignment_name: Name of the assignment
            due_date: Optional due date (ISO format)

        Returns:
            Operation name for tracking upload status
        """
        if not self.file_search_store:
            raise ValueError(
                "File Search store not initialized. Call initialize_store() first."
            )

        custom_metadata = [
            {"key": "type", "string_value": "homework"},
            {"key": "subject", "string_value": subject.lower()},
            {"key": "assignment", "string_value": assignment_name},
            {"key": "child_id", "string_value": self.child_id},
        ]

        if due_date:
            custom_metadata.append({"key": "due_date", "string_value": due_date})

        logger.info(
            "uploading_homework",
            child_id=self.child_id,
            file_name=file_path.name,
            subject=subject,
            assignment=assignment_name,
        )

        operation = self.client.file_search_stores.upload_to_file_search_store(
            file=str(file_path),
            file_search_store_name=self.file_search_store.name,
            config={
                "display_name": f"{assignment_name} - {file_path.name}",
                "custom_metadata": custom_metadata,
            },
        )

        # Wait for processing
        while not operation.done:
            await asyncio.sleep(2)
            operation = self.client.operations.get(operation)

        logger.info(
            "uploaded_homework",
            child_id=self.child_id,
            file_name=file_path.name,
            subject=subject,
            assignment=assignment_name,
            operation_name=operation.name,
        )

        return operation.name

    async def upload_study_guide(
        self, file_path: Path, subject: str, topic: str
    ) -> str:
        """
        Upload study guide or supplementary material.

        Args:
            file_path: Path to study guide file
            subject: Subject area
            topic: Specific topic covered

        Returns:
            Operation name for tracking upload status
        """
        if not self.file_search_store:
            raise ValueError(
                "File Search store not initialized. Call initialize_store() first."
            )

        custom_metadata = [
            {"key": "type", "string_value": "study_guide"},
            {"key": "subject", "string_value": subject.lower()},
            {"key": "topic", "string_value": topic},
            {"key": "child_id", "string_value": self.child_id},
        ]

        logger.info(
            "uploading_study_guide",
            child_id=self.child_id,
            file_name=file_path.name,
            subject=subject,
            topic=topic,
        )

        operation = self.client.file_search_stores.upload_to_file_search_store(
            file=str(file_path),
            file_search_store_name=self.file_search_store.name,
            config={
                "display_name": f"{topic} - {file_path.name}",
                "custom_metadata": custom_metadata,
            },
        )

        # Wait for processing
        while not operation.done:
            await asyncio.sleep(2)
            operation = self.client.operations.get(operation)

        logger.info(
            "uploaded_study_guide",
            child_id=self.child_id,
            file_name=file_path.name,
            subject=subject,
            topic=topic,
            operation_name=operation.name,
        )

        return operation.name

    def list_materials(
        self, material_type: str | None = None, subject: str | None = None
    ) -> list[types.Document]:
        """
        List uploaded materials with optional filters.

        Args:
            material_type: Filter by type (textbook, homework, study_guide)
            subject: Filter by subject

        Returns:
            List of Document objects matching filters

        Example:
            >>> # Get all math textbooks
            >>> math_books = manager.list_materials(
            ...     material_type="textbook",
            ...     subject="math"
            ... )
        """
        if not self.file_search_store:
            raise ValueError(
                "File Search store not initialized. Call initialize_store() first."
            )

        # Build metadata filter
        filters = []
        if material_type:
            filters.append(f"type={material_type}")
        if subject:
            filters.append(f"subject={subject.lower()}")

        metadata_filter = " AND ".join(filters) if filters else None

        logger.info(
            "listing_materials",
            child_id=self.child_id,
            material_type=material_type,
            subject=subject,
            filter=metadata_filter,
        )

        try:
            documents = self.client.file_search_stores.documents.list(
                file_search_store_name=self.file_search_store.name,
                metadata_filter=metadata_filter,
            )

            result = list(documents)

            logger.info("listed_materials", child_id=self.child_id, count=len(result))

            return result
        except Exception as e:
            logger.error(
                "error_listing_materials", child_id=self.child_id, error=str(e)
            )
            return []

    def delete_material(self, document_name: str) -> bool:
        """
        Delete a specific material from the store.

        Args:
            document_name: Full document name to delete

        Returns:
            True if successful, False otherwise
        """
        if not self.file_search_store:
            raise ValueError(
                "File Search store not initialized. Call initialize_store() first."
            )

        try:
            self.client.file_search_stores.documents.delete(name=document_name)

            logger.info(
                "deleted_material", child_id=self.child_id, document_name=document_name
            )

            return True
        except Exception as e:
            logger.error(
                "error_deleting_material",
                child_id=self.child_id,
                document_name=document_name,
                error=str(e),
            )
            return False

    def get_file_search_tool(
        self, subject: str | None = None, material_type: str | None = None
    ) -> types.Tool:
        """
        Get a configured File Search tool for use in generate_content.

        Args:
            subject: Optional subject filter
            material_type: Optional material type filter

        Returns:
            Tool configured for File Search with appropriate filters

        Example:
            >>> tool = manager.get_file_search_tool(subject="math")
            >>> response = client.models.generate_content(
            ...     model="gemini-2.5-flash",
            ...     contents="Explain fractions",
            ...     config=GenerateContentConfig(tools=[tool])
            ... )
        """
        if not self.file_search_store:
            raise ValueError(
                "File Search store not initialized. Call initialize_store() first."
            )

        # Build metadata filter
        filters = [f"child_id={self.child_id}"]  # Always filter by child

        if material_type:
            filters.append(f"type={material_type}")
        if subject:
            filters.append(f"subject={subject.lower()}")

        metadata_filter = " AND ".join(filters)

        # Type assertion: file_search_store is guaranteed to be initialized
        # by the check at the beginning of this method
        assert self.file_search_store is not None
        assert self.file_search_store.name is not None

        return types.Tool(
            file_search=types.FileSearch(
                file_search_store_names=[self.file_search_store.name],
                metadata_filter=metadata_filter,
            )
        )
