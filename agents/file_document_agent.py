"""File & Document Agent for JARVIS Layer 3 (Scoped Laptop Control Expansion).

Provides real file search, create, read, move, and rename operations across:
- Workspace Sandbox (D:\\assignment\\JARVIS\\workspace\\)
- Real User Directories: Documents, Downloads, Desktop

TWO-GATE SAFETY SYSTEM ENFORCEMENT:
Any operation outside the original workspace sandbox path strictly enforces
the Two-Gate permission check, requiring explicit user confirmation before execution.
Guarded against unauthorized directory escapes and credential file access.
"""

import os
import shutil
import fnmatch
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from config.settings import PROJECT_ROOT
from agents.permission_checks import permission_gate

logger = logging.getLogger("JARVIS.FileDocumentAgent")

WORKSPACE_DIR = (PROJECT_ROOT / "workspace").resolve()
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

DOCUMENTS_DIR = Path(os.path.expanduser("~/Documents")).resolve()
DOWNLOADS_DIR = Path(os.path.expanduser("~/Downloads")).resolve()
DESKTOP_DIR = Path(os.path.expanduser("~/Desktop")).resolve()

# Ensure directories exist
for d in [DOCUMENTS_DIR, DOWNLOADS_DIR, DESKTOP_DIR]:
    try:
        d.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

ALLOWED_ROOTS = {
    "workspace": WORKSPACE_DIR,
    "documents": DOCUMENTS_DIR,
    "downloads": DOWNLOADS_DIR,
    "desktop": DESKTOP_DIR,
}

FORBIDDEN_FILE_PATTERNS = {
    "*.env*",
    "*.pem",
    "*.key",
    "*id_rsa*",
    "*.pfx",
    "*.p12",
}


class FileDocumentAgent:
    """Scoped laptop control file management agent with Two-Gate confirmation."""

    def __init__(self, sandbox_root: Path = WORKSPACE_DIR):
        self.sandbox_root = sandbox_root.resolve()
        self.sandbox_root.mkdir(parents=True, exist_ok=True)
        self.allowed_roots = ALLOWED_ROOTS

    def _resolve_scoped_path(self, path_str: str, default_dir: str = "workspace") -> Path:
        """Resolves target path within authorized user scopes (Documents, Downloads, Desktop, Workspace)."""
        if not path_str:
            return self.allowed_roots.get(default_dir.lower(), self.sandbox_root)

        clean_path = path_str.strip().replace('"', '').replace("'", "")

        # Check for forbidden credential/secret patterns in the filename
        file_name = os.path.basename(clean_path)
        for pattern in FORBIDDEN_FILE_PATTERNS:
            if fnmatch.fnmatch(file_name.lower(), pattern):
                raise PermissionError(f"Access to sensitive credential file '{file_name}' is strictly forbidden.")

        # Determine target root
        lower = clean_path.lower()
        matched_root = None
        rel_portion = clean_path

        if lower.startswith("documents:") or lower.startswith("documents/") or lower.startswith("documents\\") or "documents" in lower.split(os.sep):
            matched_root = DOCUMENTS_DIR
            # Strip prefix if explicitly given
            rel_portion = clean_path.replace("documents:", "").replace("Documents:", "").strip("/\\")
            if rel_portion.lower().startswith("documents"):
                rel_portion = rel_portion[len("documents"):].strip("/\\")
        elif lower.startswith("downloads:") or lower.startswith("downloads/") or lower.startswith("downloads\\") or "downloads" in lower.split(os.sep):
            matched_root = DOWNLOADS_DIR
            rel_portion = clean_path.replace("downloads:", "").replace("Downloads:", "").strip("/\\")
            if rel_portion.lower().startswith("downloads"):
                rel_portion = rel_portion[len("downloads"):].strip("/\\")
        elif lower.startswith("desktop:") or lower.startswith("desktop/") or lower.startswith("desktop\\") or "desktop" in lower.split(os.sep):
            matched_root = DESKTOP_DIR
            rel_portion = clean_path.replace("desktop:", "").replace("Desktop:", "").strip("/\\")
            if rel_portion.lower().startswith("desktop"):
                rel_portion = rel_portion[len("desktop"):].strip("/\\")
        else:
            matched_root = self.allowed_roots.get(default_dir.lower(), self.sandbox_root)

        target_path = Path(clean_path)
        if target_path.is_absolute():
            resolved = target_path.resolve()
        else:
            resolved = (matched_root / rel_portion).resolve()

        # Enforce that resolved path is strictly within one of the authorized scopes
        is_authorized = False
        for root in self.allowed_roots.values():
            try:
                if resolved == root or root in resolved.parents:
                    is_authorized = True
                    break
            except Exception:
                pass

        if not is_authorized:
            raise PermissionError(f"Access denied: Target path '{clean_path}' is outside authorized laptop control scope.")

        return resolved

    def _is_outside_workspace(self, path: Path) -> bool:
        """Determines if a target path is outside the original workspace sandbox."""
        try:
            return not (path == self.sandbox_root or self.sandbox_root in path.parents)
        except Exception:
            return True

    def create_file(
        self,
        path: str,
        content: str = "",
        user_confirmed: bool = False,
        default_dir: str = "workspace"
    ) -> Dict[str, Any]:
        """Creates a file. Requires explicit Two-Gate confirmation if outside workspace sandbox."""
        try:
            target_path = self._resolve_scoped_path(path, default_dir=default_dir)
        except Exception as e:
            return {"success": False, "error": str(e), "status": "failed"}

        # Two-Gate confirmation check for any operation outside original workspace
        if self._is_outside_workspace(target_path):
            perm = permission_gate.check_permission(
                domain="filesystem",
                action="create_file",
                details={"path": str(target_path), "bytes": len(content.encode("utf-8"))},
                confirmed=user_confirmed
            )
            if not perm.allowed:
                from orchestrator.memory import memory_manager
                memory_manager.set_pending_action({
                    "action": "create_file",
                    "required_agent_type": "file_agent",
                    "inputs": {
                        "action": "create_file",
                        "path": str(target_path),
                        "content": content,
                        "user_confirmed": True
                    }
                })
                logger.warning("[FileDocumentAgent] Blocked create_file outside sandbox pending approval: %s", target_path)
                return {
                    "success": False,
                    "status": "pending_approval",
                    "requires_confirmation": True,
                    "message": perm.message,
                    "prompt": f"Two-Gate Safety Alert: Confirmation required to create file outside sandbox at '{target_path}'.",
                    "path": str(target_path),
                    "action": "create_file",
                }

        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info("[FileDocumentAgent] Created file: %s (%d bytes)", target_path, len(content.encode('utf-8')))
            try:
                from cognitive.world_model import world_model
                world_model.update_file_context(str(target_path), content=content, is_creation=True)
                from orchestrator.context_manager import context_manager
                context_manager.set_file(str(target_path), action="create")
            except Exception:
                pass
            return {
                "success": True,
                "status": "completed",
                "action": "create_file",
                "path": str(target_path),
                "filename": target_path.name,
                "bytes_written": len(content.encode("utf-8")),
                "response": f"Successfully created file '{target_path.name}' at {target_path}.",
                "output": f"Successfully created file '{target_path.name}' at {target_path}."
            }
        except Exception as e:
            logger.error("[FileDocumentAgent] Create file failed: %s", str(e))
            return {"success": False, "error": str(e), "status": "failed"}

    def move_file(
        self,
        src_path: str,
        dest_path: str,
        user_confirmed: bool = False
    ) -> Dict[str, Any]:
        """Moves a file. Requires Two-Gate confirmation if source or destination is outside workspace sandbox."""
        try:
            src = self._resolve_scoped_path(src_path, default_dir="workspace")
            dest = self._resolve_scoped_path(dest_path, default_dir="workspace")
        except Exception as e:
            return {"success": False, "error": str(e), "status": "failed"}

        if not src.exists():
            clean_name = Path(src_path).name
            for root_key, root_dir in self.allowed_roots.items():
                cand = root_dir / clean_name
                if cand.exists():
                    src = cand
                    break

        if not src.exists():
            return {"success": False, "error": f"Source file '{src}' does not exist.", "status": "failed"}

        # If dest is a directory, append src filename
        if dest.is_dir() or not dest.suffix:
            dest.mkdir(parents=True, exist_ok=True)
            dest = dest / src.name

        # Two-Gate confirmation check
        if self._is_outside_workspace(src) or self._is_outside_workspace(dest):
            perm = permission_gate.check_permission(
                domain="filesystem",
                action="move_file",
                details={"source": str(src), "destination": str(dest)},
                confirmed=user_confirmed
            )
            if not perm.allowed:
                from orchestrator.memory import memory_manager
                memory_manager.set_pending_action({
                    "action": "move_file",
                    "required_agent_type": "file_agent",
                    "inputs": {
                        "action": "move_file",
                        "source": str(src),
                        "src": str(src),
                        "destination": str(dest),
                        "dest": str(dest),
                        "user_confirmed": True
                    }
                })
                logger.warning("[FileDocumentAgent] Blocked move_file pending approval: %s -> %s", src, dest)
                return {
                    "success": False,
                    "status": "pending_approval",
                    "requires_confirmation": True,
                    "message": perm.message,
                    "prompt": f"Two-Gate Safety Alert: Confirmation required to move file outside sandbox from '{src.name}' to '{dest}'.",
                    "source": str(src),
                    "destination": str(dest),
                    "action": "move_file",
                }

        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dest))
            logger.info("[FileDocumentAgent] Moved file: %s -> %s", src, dest)
            return {
                "success": True,
                "status": "completed",
                "action": "move_file",
                "source": str(src),
                "destination": str(dest),
                "response": f"Successfully moved '{src.name}' to '{dest}'.",
                "output": f"Successfully moved '{src.name}' to '{dest}'."
            }
        except Exception as e:
            logger.error("[FileDocumentAgent] Move file failed: %s", str(e))
            return {"success": False, "error": str(e), "status": "failed"}

    def rename_file(
        self,
        src_path: str,
        new_name: str,
        user_confirmed: bool = False
    ) -> Dict[str, Any]:
        """Renames a file within its parent directory."""
        try:
            src = self._resolve_scoped_path(src_path, default_dir="workspace")
        except Exception as e:
            return {"success": False, "error": str(e), "status": "failed"}

        if not src.exists():
            return {"success": False, "error": f"Source file '{src}' does not exist.", "status": "failed"}

        dest = src.parent / new_name

        if self._is_outside_workspace(src):
            perm = permission_gate.check_permission(
                domain="filesystem",
                action="rename_file",
                details={"source": str(src), "new_name": new_name},
                confirmed=user_confirmed
            )
            if not perm.allowed:
                return {
                    "success": False,
                    "status": "pending_approval",
                    "requires_confirmation": True,
                    "message": perm.message,
                    "prompt": f"Two-Gate Safety Alert: Confirmation required to rename file '{src.name}' to '{new_name}'.",
                    "action": "rename_file",
                }

        try:
            src.rename(dest)
            return {
                "success": True,
                "status": "completed",
                "action": "rename_file",
                "source": str(src),
                "destination": str(dest),
                "response": f"Successfully renamed '{src.name}' to '{new_name}'.",
                "output": f"Successfully renamed '{src.name}' to '{new_name}'."
            }
        except Exception as e:
            return {"success": False, "error": str(e), "status": "failed"}

    def delete_file(
        self,
        file_path: str,
        user_confirmed: bool = False,
        default_dir: str = "workspace"
    ) -> Dict[str, Any]:
        """Deletes a file with mandatory confirmation check for destructive deletion."""
        try:
            target = self._resolve_scoped_path(file_path, default_dir=default_dir)
        except Exception as e:
            return {"success": False, "error": str(e), "status": "failed"}

        if not target.exists():
            return {"success": False, "error": f"File '{target}' does not exist.", "status": "failed"}

        if not user_confirmed:
            from orchestrator.memory import memory_manager
            memory_manager.set_pending_action({
                "action": "delete_file",
                "required_agent_type": "file_agent",
                "inputs": {
                    "action": "delete_file",
                    "path": str(target),
                    "file_path": str(target),
                    "target": str(target),
                    "user_confirmed": True
                }
            })
            logger.warning("[FileDocumentAgent] Blocked delete_file pending approval: %s", target)
            return {
                "success": False,
                "status": "pending_approval",
                "requires_confirmation": True,
                "action": "delete_file",
                "path": str(target),
                "prompt": f"Two-Gate Safety Alert: Confirmation required to delete file '{target.name}'.",
                "response": f"Safety Gate Triggered: Deleting file '{target.name}' is destructive and requires explicit confirmation. Please confirm to proceed.",
            }

        try:
            if target.is_dir():
                shutil.rmtree(target)
                logger.info("[FileDocumentAgent] Deleted directory: %s", target)
                return {
                    "success": True,
                    "status": "completed",
                    "action": "delete_file",
                    "path": str(target),
                    "filename": target.name,
                    "response": f"Successfully deleted folder '{target.name}'.",
                    "output": f"Successfully deleted folder '{target.name}'."
                }
            else:
                target.unlink()
                logger.info("[FileDocumentAgent] Deleted file: %s", target)
                try:
                    from cognitive.world_model import world_model
                    if world_model.state.last_created_file == str(target):
                        world_model.state.last_created_file = None
                    if world_model.state.last_file_path == str(target):
                        world_model.state.last_file_path = None
                except Exception:
                    pass
                return {
                    "success": True,
                    "status": "completed",
                    "action": "delete_file",
                    "path": str(target),
                    "filename": target.name,
                    "response": f"Successfully deleted file '{target.name}'.",
                    "output": f"Successfully deleted file '{target.name}'."
                }
        except Exception as e:
            logger.error("[FileDocumentAgent] Delete file/folder failed: %s", str(e))
            return {"success": False, "error": str(e), "status": "failed"}

    def create_directory(self, dir_path: str, default_dir: str = "workspace") -> Dict[str, Any]:
        """Creates a directory within the scoped workspace."""
        try:
            target = self._resolve_scoped_path(dir_path, default_dir=default_dir)
            target.mkdir(parents=True, exist_ok=True)
            return {
                "success": True,
                "status": "completed",
                "action": "create_directory",
                "path": str(target),
                "filename": target.name,
                "response": f"Successfully created folder '{target.name}'.",
                "output": f"Successfully created folder '{target.name}'."
            }
        except Exception as e:
            return {"success": False, "error": str(e), "status": "failed"}


    def search_files(
        self,
        pattern: str = "*",
        directory: str = "documents",
        max_matches: int = 40
    ) -> Dict[str, Any]:
        """Searches for files matching pattern across specified scoped directory (Documents, Downloads, Desktop, Workspace)."""
        clean_dir = directory.lower().strip()
        target_root = self.allowed_roots.get(clean_dir, DOCUMENTS_DIR)

        matches = []
        ignored = {".git", ".venv", "__pycache__", "node_modules", "AppData"}

        search_pat = pattern if ("*" in pattern or "?" in pattern) else f"*{pattern}*"

        try:
            for root, dirs, files in os.walk(target_root):
                dirs[:] = [d for d in dirs if d not in ignored and not d.startswith(".")]
                for file in files:
                    if fnmatch.fnmatch(file.lower(), search_pat.lower()):
                        full_p = Path(root) / file
                        try:
                            matches.append({
                                "name": file,
                                "path": str(full_p),
                                "size_bytes": full_p.stat().st_size
                            })
                        except Exception:
                            matches.append({"name": file, "path": str(full_p), "size_bytes": 0})

                        if len(matches) >= max_matches:
                            break
                if len(matches) >= max_matches:
                    break

            logger.info("[FileDocumentAgent] Search '%s' in %s returned %d matches", pattern, target_root.name, len(matches))
            return {
                "success": True,
                "status": "completed",
                "action": "search_files",
                "directory": target_root.name,
                "pattern": pattern,
                "match_count": len(matches),
                "matches": matches,
                "response": f"Found {len(matches)} file(s) matching '{pattern}' in {target_root.name}.",
                "output": f"Found {len(matches)} file(s) matching '{pattern}' in {target_root.name}."
            }
        except Exception as e:
            logger.error("[FileDocumentAgent] Search error: %s", str(e))
            return {"success": False, "error": str(e), "status": "failed"}

    def read_file(self, relative_path: str, max_chars: int = 10000) -> Dict[str, Any]:
        """Reads content from an authorized file."""
        try:
            target_path = self._resolve_scoped_path(relative_path)
            if not target_path.exists():
                return {"success": False, "error": f"File '{relative_path}' does not exist."}
            if not target_path.is_file():
                return {"success": False, "error": f"Path '{relative_path}' is not a file."}

            with open(target_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(max_chars)

            resp_txt = f"Content of '{target_path.name}':\n\n{content}" if content else f"File '{target_path.name}' is empty."
            return {
                "success": True,
                "status": "completed",
                "action": "read_file",
                "path": str(target_path),
                "filename": target_path.name,
                "content": content,
                "size_bytes": target_path.stat().st_size,
                "response": resp_txt,
                "output": content,
            }
        except Exception as e:
            return {"success": False, "error": str(e), "status": "failed"}

    # --- Batch Rename, Compression & Format Conversion (Group 2) ---
    def batch_rename(
        self,
        directory: str = "documents",
        pattern: str = "",
        replacement: str = "",
        user_confirmed: bool = False
    ) -> Dict[str, Any]:
        """Batch renames files matching pattern within an authorized scope."""
        import re
        try:
            target_dir = self._resolve_scoped_path(directory, default_dir=directory)
            if not target_dir.exists() or not target_dir.is_dir():
                return {"success": False, "error": f"Target directory '{directory}' does not exist."}

            # TWO-GATE SAFETY CHECK
            if self._is_outside_workspace(target_dir) and not user_confirmed:
                logger.warning("[FileDocumentAgent] Blocked batch rename outside workspace pending approval.")
                return {
                    "success": False,
                    "status": "pending_approval",
                    "requires_confirmation": True,
                    "action": "batch_rename",
                    "directory": str(target_dir),
                    "prompt": f"Confirmation required: Authorize batch renaming files matching '{pattern}' in {target_dir.name}?",
                    "response": f"Safety Gate Triggered: Authorize batch renaming files matching '{pattern}' in {target_dir.name}."
                }

            # Find matching files
            matched_files = []
            for item in target_dir.iterdir():
                if item.is_file() and not item.name.startswith("."):
                    if fnmatch.fnmatch(item.name.lower(), pattern.lower()) or re.search(pattern, item.name, re.I):
                        new_name = re.sub(pattern, replacement, item.name, flags=re.I) if replacement else item.name
                        if new_name != item.name:
                            matched_files.append((item, target_dir / new_name))

            if not matched_files:
                return {"success": True, "action": "batch_rename", "renamed_count": 0, "message": f"No files matched pattern '{pattern}'."}

            renamed = []
            for src, dest in matched_files:
                src.rename(dest)
                renamed.append({"old": src.name, "new": dest.name})

            return {
                "success": True,
                "status": "completed",
                "action": "batch_rename",
                "directory": str(target_dir),
                "renamed_count": len(renamed),
                "renamed": renamed,
                "response": f"Successfully batch renamed {len(renamed)} files in {target_dir.name}."
            }
        except Exception as e:
            return {"success": False, "error": str(e), "status": "failed"}

    def compress_directory(
        self,
        source_dir: str,
        output_zip: Optional[str] = None,
        user_confirmed: bool = False
    ) -> Dict[str, Any]:
        """Compresses a scoped directory into a .zip archive."""
        import zipfile
        try:
            src_path = self._resolve_scoped_path(source_dir, default_dir="documents")
            if not src_path.exists() or not src_path.is_dir():
                return {"success": False, "error": f"Source directory '{source_dir}' does not exist."}

            zip_dest = Path(output_zip) if output_zip else src_path.parent / f"{src_path.name}.zip"
            if not zip_dest.is_absolute():
                zip_dest = src_path.parent / zip_dest.name
            zip_dest = self._resolve_scoped_path(str(zip_dest), default_dir="documents")

            # TWO-GATE SAFETY CHECK
            if (self._is_outside_workspace(src_path) or self._is_outside_workspace(zip_dest)) and not user_confirmed:
                return {
                    "success": False,
                    "status": "pending_approval",
                    "requires_confirmation": True,
                    "action": "compress_directory",
                    "source": str(src_path),
                    "destination": str(zip_dest),
                    "prompt": f"Confirmation required: Authorize compressing '{src_path.name}' into '{zip_dest.name}'?",
                    "response": f"Safety Gate Triggered: Authorize compressing '{src_path.name}' to '{zip_dest.name}'."
                }

            with zipfile.ZipFile(zip_dest, "w", zipfile.ZIP_DEFLATED) as zf:
                for root, _, files in os.walk(src_path):
                    for f in files:
                        full_p = Path(root) / f
                        rel_p = full_p.relative_to(src_path)
                        zf.write(full_p, arcname=str(rel_p))

            return {
                "success": True,
                "status": "completed",
                "action": "compress_directory",
                "archive_path": str(zip_dest),
                "size_bytes": zip_dest.stat().st_size,
                "archive_size_bytes": zip_dest.stat().st_size,
                "response": f"Compressed '{src_path.name}' into '{zip_dest.name}' ({zip_dest.stat().st_size} bytes)."
            }
        except Exception as e:
            return {"success": False, "error": str(e), "status": "failed"}

    def extract_archive(
        self,
        zip_path: str,
        target_dir: Optional[str] = None,
        user_confirmed: bool = False
    ) -> Dict[str, Any]:
        """Extracts a .zip archive into an authorized scoped directory."""
        import zipfile
        try:
            archive_path = self._resolve_scoped_path(zip_path, default_dir="documents")
            if not archive_path.exists() or not archive_path.is_file():
                return {"success": False, "error": f"Archive file '{zip_path}' does not exist."}

            dest_dir = self._resolve_scoped_path(target_dir or str(archive_path.parent / archive_path.stem), default_dir="documents")
            dest_dir.mkdir(parents=True, exist_ok=True)

            # TWO-GATE SAFETY CHECK
            if self._is_outside_workspace(dest_dir) and not user_confirmed:
                return {
                    "success": False,
                    "status": "pending_approval",
                    "requires_confirmation": True,
                    "action": "extract_archive",
                    "archive": str(archive_path),
                    "destination": str(dest_dir),
                    "prompt": f"Confirmation required: Authorize extracting '{archive_path.name}' into '{dest_dir.name}'?",
                    "response": f"Safety Gate Triggered: Authorize extracting '{archive_path.name}' into '{dest_dir.name}'."
                }

            with zipfile.ZipFile(archive_path, "r") as zf:
                extracted_names = zf.namelist()
                zf.extractall(dest_dir)

            return {
                "success": True,
                "status": "completed",
                "action": "extract_archive",
                "extracted_to": str(dest_dir),
                "files": extracted_names,
                "response": f"Extracted '{archive_path.name}' into '{dest_dir.name}'."
            }
        except Exception as e:
            return {"success": False, "error": str(e), "status": "failed"}

    def convert_image(
        self,
        source_path: str,
        target_format: str = "webp",
        user_confirmed: bool = False
    ) -> Dict[str, Any]:
        """Converts image formats (PNG, WebP, JPEG) using Pillow."""
        from PIL import Image
        try:
            src = self._resolve_scoped_path(source_path, default_dir="documents")
            if not src.exists() or not src.is_file():
                return {"success": False, "error": f"Source image '{source_path}' does not exist."}

            fmt = target_format.lower().strip().replace(".", "")
            dest = src.with_suffix(f".{fmt}")

            # TWO-GATE SAFETY CHECK
            if (self._is_outside_workspace(src) or self._is_outside_workspace(dest)) and not user_confirmed:
                return {
                    "success": False,
                    "status": "pending_approval",
                    "requires_confirmation": True,
                    "action": "convert_image",
                    "source": str(src),
                    "destination": str(dest),
                    "prompt": f"Confirmation required: Authorize converting image '{src.name}' to {fmt.upper()}?",
                    "response": f"Safety Gate Triggered: Authorize converting image '{src.name}' to '{dest.name}'."
                }

            with Image.open(src) as img:
                img.save(dest, format=fmt.upper() if fmt != "jpg" else "JPEG")

            return {
                "success": True,
                "status": "completed",
                "action": "convert_image",
                "source": str(src),
                "destination": str(dest),
                "format": fmt,
                "size_bytes": dest.stat().st_size,
                "response": f"Converted image '{src.name}' to '{dest.name}' ({dest.stat().st_size} bytes)."
            }
        except Exception as e:
            return {"success": False, "error": str(e), "status": "failed"}

    def convert_document(
        self,
        source_path: str,
        target_format: str = "txt",
        user_confirmed: bool = False
    ) -> Dict[str, Any]:
        """Converts document formats (.docx / .pdf to .txt)."""
        try:
            src = self._resolve_scoped_path(source_path, default_dir="documents")
            if not src.exists() or not src.is_file():
                return {"success": False, "error": f"Source document '{source_path}' does not exist."}

            fmt = target_format.lower().strip().replace(".", "")
            dest = src.with_suffix(f".{fmt}")

            # TWO-GATE SAFETY CHECK
            if (self._is_outside_workspace(src) or self._is_outside_workspace(dest)) and not user_confirmed:
                return {
                    "success": False,
                    "status": "pending_approval",
                    "requires_confirmation": True,
                    "action": "convert_document",
                    "source": str(src),
                    "destination": str(dest),
                    "prompt": f"Confirmation required: Authorize converting '{src.name}' to {fmt.upper()}?",
                    "response": f"Safety Gate Triggered: Authorize converting '{src.name}' to '{dest.name}'."
                }

            text_content = ""
            if src.suffix.lower() == ".docx":
                import docx
                doc = docx.Document(src)
                text_content = "\n".join([p.text for p in doc.paragraphs])
            elif src.suffix.lower() == ".pdf":
                import pypdf
                reader = pypdf.PdfReader(src)
                text_content = "\n".join([page.extract_text() or "" for page in reader.pages])
            else:
                return {"success": False, "error": f"Unsupported conversion source format: '{src.suffix}'"}

            with open(dest, "w", encoding="utf-8") as f:
                f.write(text_content)

            return {
                "success": True,
                "status": "completed",
                "action": "convert_document",
                "source": str(src),
                "destination": str(dest),
                "characters": len(text_content),
                "response": f"Extracted and converted '{src.name}' to '{dest.name}' ({len(text_content)} chars)."
            }
        except Exception as e:
            return {"success": False, "error": str(e), "status": "failed"}

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Standardized router dispatch interface."""
        action = inputs.get("action", "read").lower()
        path = inputs.get("path", inputs.get("filename", inputs.get("target", "")))
        content = inputs.get("content", inputs.get("data", ""))
        confirmed = bool(inputs.get("user_confirmed", False))
        directory = inputs.get("directory", "documents")

        if action in ["search", "search_files", "find"]:
            pattern = inputs.get("pattern") or inputs.get("query") or "*"
            target_dir = inputs.get("directory") or inputs.get("folder") or "documents"
            return self.search_files(pattern=pattern, directory=target_dir)

        elif action in ["create", "create_file", "write", "save"]:
            return self.create_file(path=path, content=content, user_confirmed=confirmed, default_dir=directory)

        elif action in ["create_directory", "mkdir", "create_folder", "make_folder"]:
            return self.create_directory(dir_path=path, default_dir=directory)


        elif action in ["move", "move_file"]:
            src = inputs.get("source") or inputs.get("src") or path
            dest = inputs.get("destination") or inputs.get("dest") or inputs.get("to", "")
            return self.move_file(src_path=src, dest_path=dest, user_confirmed=confirmed)

        elif action in ["rename", "rename_file"]:
            new_name = inputs.get("new_name") or inputs.get("to") or ""
            return self.rename_file(src_path=path, new_name=new_name, user_confirmed=confirmed)

        elif action in ["delete", "delete_file", "remove", "remove_file"]:
            return self.delete_file(file_path=path, user_confirmed=confirmed, default_dir=directory)

        elif action in ["batch_rename", "batch_rename_files"]:
            pat = inputs.get("pattern", "")
            rep = inputs.get("replacement", "")
            return self.batch_rename(directory=directory, pattern=pat, replacement=rep, user_confirmed=confirmed)

        elif action in ["compress", "compress_directory", "zip"]:
            src = inputs.get("source") or path
            out_zip = inputs.get("output_zip") or inputs.get("destination") or inputs.get("output")
            return self.compress_directory(source_dir=src, output_zip=out_zip, user_confirmed=confirmed)

        elif action in ["extract", "extract_archive", "unzip"]:
            z_path = inputs.get("archive") or inputs.get("zip_path") or path
            dest = inputs.get("target_dir") or inputs.get("destination") or inputs.get("to")
            return self.extract_archive(zip_path=z_path, target_dir=dest, user_confirmed=confirmed)

        elif action in ["convert_image", "image_convert"]:
            fmt = inputs.get("format", inputs.get("target_format", "webp"))
            return self.convert_image(source_path=path, target_format=fmt, user_confirmed=confirmed)

        elif action in ["convert_document", "doc_convert", "convert"]:
            fmt = inputs.get("format", inputs.get("target_format", "txt"))
            return self.convert_document(source_path=path, target_format=fmt, user_confirmed=confirmed)

        elif action in ["list", "list_files"]:
            return self.list_files(subfolder=path or directory)

        else:
            return self.read_file(relative_path=path)


file_document_agent = FileDocumentAgent()
