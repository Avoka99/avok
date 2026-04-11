"""Storage service for handling file uploads to S3 or local storage."""
import os
import uuid
import logging
from typing import Optional
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """Service for handling file uploads and storage."""
    
    def __init__(self):
        """Initialize storage service."""
        self.storage_type = "local"  # Use local storage for development
        self.upload_dir = Path("uploads")
        self.upload_dir.mkdir(exist_ok=True)
    
    async def upload_file(
        self,
        file,
        folder: str = "general",
        user_id: Optional[int] = None
    ) -> str:
        """
        Upload a file to storage.
        
        Args:
            file: The file to upload (FastAPI UploadFile)
            folder: Subfolder to store the file in
            user_id: Optional user ID for organization
            
        Returns:
            URL of the uploaded file
        """
        try:
            # Generate unique filename
            file_extension = os.path.splitext(file.filename)[1]
            unique_id = uuid.uuid4().hex
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            
            if user_id:
                filename = f"{user_id}_{timestamp}_{unique_id}{file_extension}"
            else:
                filename = f"{timestamp}_{unique_id}{file_extension}"
            
            # Create folder path
            folder_path = self.upload_dir / folder
            folder_path.mkdir(parents=True, exist_ok=True)
            
            # Save file
            file_path = folder_path / filename
            
            content = await file.read()
            with open(file_path, "wb") as f:
                f.write(content)
            
            # Return relative URL
            file_url = f"/uploads/{folder}/{filename}"
            
            logger.info(f"File uploaded: {file_url}")
            return file_url
            
        except Exception as e:
            logger.error(f"Failed to upload file: {e}")
            raise Exception(f"File upload failed: {str(e)}")
    
    async def delete_file(self, file_url: str) -> bool:
        """
        Delete a file from storage.
        
        Args:
            file_url: URL of the file to delete
            
        Returns:
            True if deleted successfully
        """
        try:
            # Extract relative path from URL
            if file_url.startswith("/uploads/"):
                relative_path = file_url[9:]  # Remove '/uploads/'
                file_path = self.upload_dir / relative_path
                
                if file_path.exists():
                    file_path.unlink()
                    logger.info(f"File deleted: {file_url}")
                    return True
                else:
                    logger.warning(f"File not found: {file_url}")
                    return False
            return False
            
        except Exception as e:
            logger.error(f"Failed to delete file: {e}")
            return False
    
    async def get_file_path(self, file_url: str) -> Optional[Path]:
        """
        Get the local file path for a URL.
        
        Args:
            file_url: URL of the file
            
        Returns:
            Path object if file exists, None otherwise
        """
        if file_url.startswith("/uploads/"):
            relative_path = file_url[9:]
            file_path = self.upload_dir / relative_path
            
            if file_path.exists():
                return file_path
        
        return None
    
    async def upload_multiple(
        self,
        files: list,
        folder: str = "general",
        user_id: Optional[int] = None
    ) -> list:
        """
        Upload multiple files.
        
        Args:
            files: List of files to upload
            folder: Subfolder to store files in
            user_id: Optional user ID
            
        Returns:
            List of uploaded file URLs
        """
        urls = []
        for file in files:
            url = await self.upload_file(file, folder, user_id)
            urls.append(url)
        return urls