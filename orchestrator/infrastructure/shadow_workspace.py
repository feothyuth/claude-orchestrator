"""
Docker-based isolated workspace for safe code verification.
Implements the Cursor-style Shadow Workspace pattern.
"""

import docker
import json
import tempfile
import shutil
import subprocess
import logging
from pathlib import Path
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, asdict
from enum import Enum
from contextlib import contextmanager

# Configure logging
logger = logging.getLogger(__name__)


class VerificationResult(Enum):
    """Verification outcome status."""
    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"


@dataclass
class DiagnosticItem:
    """Individual diagnostic message from verification tools."""
    file: str
    line: int
    severity: str  # error, warning, info
    message: str
    rule_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)


@dataclass
class VerificationReport:
    """Complete verification report from a single check."""
    status: VerificationResult
    diagnostics: List[DiagnosticItem]
    stdout: str
    stderr: str
    exit_code: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'status': self.status.value,
            'diagnostics': [d.to_dict() for d in self.diagnostics],
            'stdout': self.stdout,
            'stderr': self.stderr,
            'exit_code': self.exit_code
        }

    def has_errors(self) -> bool:
        """Check if report contains any errors."""
        return any(d.severity == 'error' for d in self.diagnostics)

    def summary(self) -> str:
        """Generate human-readable summary."""
        error_count = sum(1 for d in self.diagnostics if d.severity == 'error')
        warning_count = sum(1 for d in self.diagnostics if d.severity == 'warning')
        return f"Status: {self.status.value}, Errors: {error_count}, Warnings: {warning_count}"


class ShadowWorkspaceError(Exception):
    """Base exception for shadow workspace operations."""
    pass


class ContainerError(ShadowWorkspaceError):
    """Docker container operation failed."""
    pass


class VerificationError(ShadowWorkspaceError):
    """Verification check failed to run."""
    pass


class ShadowWorkspace:
    """
    Docker-based isolated workspace for safe code verification.

    Features:
    - Isolated Docker environment
    - Multi-language linting and type checking
    - Security scanning
    - Test execution
    - Safe diff generation and commit

    Example:
        with ShadowWorkspace('/path/to/project') as shadow:
            shadow.write_file('main.py', 'print("hello")')
            results = shadow.verify_all()
            if all(r.status == VerificationResult.PASS for r in results.values()):
                shadow.commit_to_main()
    """

    def __init__(
        self,
        project_path: str,
        image: str = "orchestrator-shadow:latest",
        auto_build: bool = True,
        timeout: int = 300
    ):
        """
        Initialize shadow workspace.

        Args:
            project_path: Path to project to verify
            image: Docker image name
            auto_build: Automatically build image if missing
            timeout: Command timeout in seconds
        """
        self.project_path = Path(project_path).resolve()
        self.image = image
        self.auto_build = auto_build
        self.timeout = timeout
        self.client = None
        self.container = None
        self.shadow_path = None
        self._created = False

        if not self.project_path.exists():
            raise ShadowWorkspaceError(f"Project path does not exist: {self.project_path}")

        logger.info(f"Initialized ShadowWorkspace for {self.project_path}")

    def _ensure_docker_client(self):
        """Ensure Docker client is initialized."""
        if self.client is None:
            try:
                self.client = docker.from_env()
                self.client.ping()
            except Exception as e:
                raise ContainerError(f"Failed to connect to Docker: {e}")

    def _ensure_image(self):
        """Ensure Docker image exists, build if necessary."""
        self._ensure_docker_client()

        try:
            self.client.images.get(self.image)
            logger.info(f"Docker image {self.image} found")
        except docker.errors.ImageNotFound:
            if not self.auto_build:
                raise ContainerError(f"Docker image {self.image} not found and auto_build=False")

            logger.info(f"Building Docker image {self.image}...")
            self._build_image()

    def _build_image(self):
        """Build the shadow workspace Docker image."""
        dockerfile_path = Path(__file__).parent / "Dockerfile.shadow"

        if not dockerfile_path.exists():
            raise ContainerError(f"Dockerfile not found at {dockerfile_path}")

        try:
            build_path = dockerfile_path.parent
            self.client.images.build(
                path=str(build_path),
                dockerfile=dockerfile_path.name,
                tag=self.image,
                rm=True
            )
            logger.info(f"Successfully built image {self.image}")
        except Exception as e:
            raise ContainerError(f"Failed to build Docker image: {e}")

    def create(self) -> str:
        """
        Create isolated shadow workspace.

        Returns:
            Path to shadow workspace directory
        """
        if self._created:
            logger.warning("Shadow workspace already created")
            return str(self.shadow_path)

        self._ensure_image()

        # Create temporary directory for shadow workspace
        self.shadow_path = Path(tempfile.mkdtemp(prefix="shadow_workspace_"))
        logger.info(f"Created shadow workspace at {self.shadow_path}")

        # Copy project files to shadow workspace
        try:
            self._copy_project_files()
        except Exception as e:
            shutil.rmtree(self.shadow_path, ignore_errors=True)
            raise ShadowWorkspaceError(f"Failed to copy project files: {e}")

        # Start Docker container
        try:
            self.container = self.client.containers.run(
                self.image,
                detach=True,
                volumes={
                    str(self.shadow_path): {'bind': '/workspace', 'mode': 'rw'}
                },
                working_dir='/workspace',
                remove=False,
                name=f"shadow-{self.shadow_path.name}"
            )
            logger.info(f"Started container {self.container.id[:12]}")
        except Exception as e:
            shutil.rmtree(self.shadow_path, ignore_errors=True)
            raise ContainerError(f"Failed to start container: {e}")

        self._created = True
        return str(self.shadow_path)

    def _copy_project_files(self):
        """Copy project files to shadow workspace, excluding common ignore patterns."""
        ignore_patterns = shutil.ignore_patterns(
            '__pycache__', '*.pyc', '.git', '.venv', 'venv',
            'node_modules', '.pytest_cache', '.mypy_cache',
            '*.egg-info', 'dist', 'build', '.DS_Store'
        )

        for item in self.project_path.iterdir():
            src = self.project_path / item.name
            dst = self.shadow_path / item.name

            try:
                if src.is_dir():
                    shutil.copytree(src, dst, ignore=ignore_patterns)
                else:
                    shutil.copy2(src, dst)
            except Exception as e:
                logger.warning(f"Failed to copy {src}: {e}")

    def apply_patch(self, patch: str) -> bool:
        """
        Apply a unified diff patch to the shadow workspace.

        Args:
            patch: Unified diff format patch string

        Returns:
            True if patch applied successfully
        """
        if not self._created:
            raise ShadowWorkspaceError("Shadow workspace not created")

        patch_file = self.shadow_path / ".shadow_patch.diff"

        try:
            patch_file.write_text(patch)

            result = self._exec_command([
                'patch', '-p1', '-i', '/workspace/.shadow_patch.diff'
            ])

            patch_file.unlink()

            if result['exit_code'] != 0:
                logger.error(f"Patch failed: {result['stderr']}")
                return False

            logger.info("Patch applied successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to apply patch: {e}")
            return False

    def write_file(self, relative_path: str, content: str) -> bool:
        """
        Write a file to the shadow workspace.

        Args:
            relative_path: Path relative to workspace root
            content: File content

        Returns:
            True if file written successfully
        """
        if not self._created:
            raise ShadowWorkspaceError("Shadow workspace not created")

        target_path = self.shadow_path / relative_path

        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(content)
            logger.info(f"Wrote file {relative_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to write file {relative_path}: {e}")
            return False

    def read_file(self, relative_path: str) -> Optional[str]:
        """
        Read a file from the shadow workspace.

        Args:
            relative_path: Path relative to workspace root

        Returns:
            File content or None if read failed
        """
        if not self._created:
            raise ShadowWorkspaceError("Shadow workspace not created")

        target_path = self.shadow_path / relative_path

        try:
            return target_path.read_text()
        except Exception as e:
            logger.error(f"Failed to read file {relative_path}: {e}")
            return None

    def _exec_command(
        self,
        command: List[str],
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Execute command in container.

        Args:
            command: Command and arguments
            timeout: Timeout in seconds (None for default)

        Returns:
            Dict with stdout, stderr, exit_code
        """
        if not self.container:
            raise ContainerError("Container not running")

        timeout = timeout or self.timeout

        try:
            exit_code, output = self.container.exec_run(
                command,
                demux=True,
                workdir='/workspace'
            )

            stdout = output[0].decode('utf-8') if output[0] else ""
            stderr = output[1].decode('utf-8') if output[1] else ""

            return {
                'stdout': stdout,
                'stderr': stderr,
                'exit_code': exit_code
            }

        except Exception as e:
            raise ContainerError(f"Command execution failed: {e}")

    def run_linter(self, language: str = "python") -> VerificationReport:
        """
        Run language-specific linter in shadow workspace.

        Supported languages:
        - python: ruff
        - javascript/typescript: eslint
        - rust: clippy

        Args:
            language: Programming language

        Returns:
            VerificationReport with linting results
        """
        if not self._created:
            raise ShadowWorkspaceError("Shadow workspace not created")

        logger.info(f"Running {language} linter")

        try:
            if language == "python":
                return self._run_ruff()
            elif language in ["javascript", "typescript"]:
                return self._run_eslint()
            elif language == "rust":
                return self._run_clippy()
            else:
                raise VerificationError(f"Unsupported language: {language}")
        except Exception as e:
            logger.error(f"Linter failed: {e}")
            return VerificationReport(
                status=VerificationResult.ERROR,
                diagnostics=[],
                stdout="",
                stderr=str(e),
                exit_code=-1
            )

    def _run_ruff(self) -> VerificationReport:
        """Run ruff Python linter."""
        result = self._exec_command([
            'ruff', 'check', '.', '--output-format', 'json'
        ])

        diagnostics = []

        if result['stdout']:
            try:
                ruff_output = json.loads(result['stdout'])
                for item in ruff_output:
                    diagnostics.append(DiagnosticItem(
                        file=item.get('filename', 'unknown'),
                        line=item.get('location', {}).get('row', 0),
                        severity='error' if item.get('code', '').startswith('E') else 'warning',
                        message=item.get('message', ''),
                        rule_id=item.get('code')
                    ))
            except json.JSONDecodeError:
                logger.warning("Failed to parse ruff JSON output")

        status = VerificationResult.PASS if result['exit_code'] == 0 else VerificationResult.FAIL

        return VerificationReport(
            status=status,
            diagnostics=diagnostics,
            stdout=result['stdout'],
            stderr=result['stderr'],
            exit_code=result['exit_code']
        )

    def _run_eslint(self) -> VerificationReport:
        """Run eslint for JavaScript/TypeScript."""
        result = self._exec_command([
            'eslint', '.', '--format', 'json'
        ])

        diagnostics = []

        if result['stdout']:
            try:
                eslint_output = json.loads(result['stdout'])
                for file_result in eslint_output:
                    for message in file_result.get('messages', []):
                        diagnostics.append(DiagnosticItem(
                            file=file_result.get('filePath', 'unknown'),
                            line=message.get('line', 0),
                            severity=message.get('severity') == 2 and 'error' or 'warning',
                            message=message.get('message', ''),
                            rule_id=message.get('ruleId')
                        ))
            except json.JSONDecodeError:
                logger.warning("Failed to parse eslint JSON output")

        status = VerificationResult.PASS if result['exit_code'] == 0 else VerificationResult.FAIL

        return VerificationReport(
            status=status,
            diagnostics=diagnostics,
            stdout=result['stdout'],
            stderr=result['stderr'],
            exit_code=result['exit_code']
        )

    def _run_clippy(self) -> VerificationReport:
        """Run clippy for Rust."""
        result = self._exec_command([
            'cargo', 'clippy', '--message-format', 'json'
        ])

        diagnostics = []
        # Parse cargo clippy JSON output
        # Implementation similar to ruff/eslint parsers

        status = VerificationResult.PASS if result['exit_code'] == 0 else VerificationResult.FAIL

        return VerificationReport(
            status=status,
            diagnostics=diagnostics,
            stdout=result['stdout'],
            stderr=result['stderr'],
            exit_code=result['exit_code']
        )

    def run_type_check(self, language: str = "python") -> VerificationReport:
        """
        Run type checker.

        Supported:
        - python: mypy
        - typescript: tsc

        Args:
            language: Programming language

        Returns:
            VerificationReport with type checking results
        """
        if not self._created:
            raise ShadowWorkspaceError("Shadow workspace not created")

        logger.info(f"Running {language} type checker")

        try:
            if language == "python":
                return self._run_mypy()
            elif language == "typescript":
                return self._run_tsc()
            else:
                raise VerificationError(f"Unsupported language: {language}")
        except Exception as e:
            logger.error(f"Type checker failed: {e}")
            return VerificationReport(
                status=VerificationResult.ERROR,
                diagnostics=[],
                stdout="",
                stderr=str(e),
                exit_code=-1
            )

    def _run_mypy(self) -> VerificationReport:
        """Run mypy type checker."""
        result = self._exec_command([
            'mypy', '.', '--show-error-codes', '--no-error-summary'
        ])

        diagnostics = []

        # Parse mypy output (format: file:line: error: message [code])
        for line in result['stdout'].split('\n'):
            if ':' in line and ('error:' in line or 'warning:' in line):
                parts = line.split(':', 3)
                if len(parts) >= 4:
                    diagnostics.append(DiagnosticItem(
                        file=parts[0],
                        line=int(parts[1]) if parts[1].isdigit() else 0,
                        severity='error' if 'error:' in line else 'warning',
                        message=parts[3].strip(),
                        rule_id=None
                    ))

        status = VerificationResult.PASS if result['exit_code'] == 0 else VerificationResult.FAIL

        return VerificationReport(
            status=status,
            diagnostics=diagnostics,
            stdout=result['stdout'],
            stderr=result['stderr'],
            exit_code=result['exit_code']
        )

    def _run_tsc(self) -> VerificationReport:
        """Run TypeScript compiler type checker."""
        result = self._exec_command(['tsc', '--noEmit'])

        diagnostics = []
        # Parse tsc output

        status = VerificationResult.PASS if result['exit_code'] == 0 else VerificationResult.FAIL

        return VerificationReport(
            status=status,
            diagnostics=diagnostics,
            stdout=result['stdout'],
            stderr=result['stderr'],
            exit_code=result['exit_code']
        )

    def run_tests(self, test_command: str = "pytest") -> VerificationReport:
        """
        Run test suite in shadow workspace.

        Args:
            test_command: Test command to execute

        Returns:
            VerificationReport with test results
        """
        if not self._created:
            raise ShadowWorkspaceError("Shadow workspace not created")

        logger.info(f"Running tests: {test_command}")

        try:
            result = self._exec_command(test_command.split())

            status = VerificationResult.PASS if result['exit_code'] == 0 else VerificationResult.FAIL

            return VerificationReport(
                status=status,
                diagnostics=[],
                stdout=result['stdout'],
                stderr=result['stderr'],
                exit_code=result['exit_code']
            )
        except Exception as e:
            logger.error(f"Test execution failed: {e}")
            return VerificationReport(
                status=VerificationResult.ERROR,
                diagnostics=[],
                stdout="",
                stderr=str(e),
                exit_code=-1
            )

    def run_security_scan(self) -> VerificationReport:
        """
        Run security analysis.
        Uses bandit for Python, npm audit for JavaScript.

        Returns:
            VerificationReport with security scan results
        """
        if not self._created:
            raise ShadowWorkspaceError("Shadow workspace not created")

        logger.info("Running security scan")

        # Detect project type
        if (self.shadow_path / "setup.py").exists() or (self.shadow_path / "pyproject.toml").exists():
            return self._run_bandit()
        elif (self.shadow_path / "package.json").exists():
            return self._run_npm_audit()
        else:
            logger.warning("No recognized project type for security scanning")
            return VerificationReport(
                status=VerificationResult.PASS,
                diagnostics=[],
                stdout="No security scan performed",
                stderr="",
                exit_code=0
            )

    def _run_bandit(self) -> VerificationReport:
        """Run bandit security scanner for Python."""
        result = self._exec_command([
            'bandit', '-r', '.', '-f', 'json'
        ])

        diagnostics = []

        if result['stdout']:
            try:
                bandit_output = json.loads(result['stdout'])
                for item in bandit_output.get('results', []):
                    diagnostics.append(DiagnosticItem(
                        file=item.get('filename', 'unknown'),
                        line=item.get('line_number', 0),
                        severity=item.get('issue_severity', 'info').lower(),
                        message=item.get('issue_text', ''),
                        rule_id=item.get('test_id')
                    ))
            except json.JSONDecodeError:
                logger.warning("Failed to parse bandit JSON output")

        status = VerificationResult.PASS if result['exit_code'] == 0 else VerificationResult.FAIL

        return VerificationReport(
            status=status,
            diagnostics=diagnostics,
            stdout=result['stdout'],
            stderr=result['stderr'],
            exit_code=result['exit_code']
        )

    def _run_npm_audit(self) -> VerificationReport:
        """Run npm audit for JavaScript projects."""
        result = self._exec_command([
            'npm', 'audit', '--json'
        ])

        diagnostics = []
        # Parse npm audit output

        status = VerificationResult.PASS if result['exit_code'] == 0 else VerificationResult.FAIL

        return VerificationReport(
            status=status,
            diagnostics=diagnostics,
            stdout=result['stdout'],
            stderr=result['stderr'],
            exit_code=result['exit_code']
        )

    def verify_all(self) -> Dict[str, VerificationReport]:
        """
        Run full verification gauntlet:
        1. Linter
        2. Type check
        3. Security scan
        4. Tests

        Returns:
            Dictionary mapping check name to VerificationReport
        """
        if not self._created:
            raise ShadowWorkspaceError("Shadow workspace not created")

        logger.info("Running full verification")

        results = {}

        # Detect language
        if (self.shadow_path / "setup.py").exists() or (self.shadow_path / "pyproject.toml").exists():
            language = "python"
        elif (self.shadow_path / "package.json").exists():
            language = "javascript"
        else:
            language = "python"  # default

        # Run checks
        results['linter'] = self.run_linter(language)
        results['type_check'] = self.run_type_check(language)
        results['security'] = self.run_security_scan()

        # Only run tests if previous checks passed
        if all(r.status != VerificationResult.ERROR for r in results.values()):
            results['tests'] = self.run_tests()

        # Log summary
        for check_name, report in results.items():
            logger.info(f"{check_name}: {report.summary()}")

        return results

    def get_diff(self) -> str:
        """
        Get unified diff between original and shadow.

        Returns:
            Unified diff string
        """
        if not self._created:
            raise ShadowWorkspaceError("Shadow workspace not created")

        try:
            result = subprocess.run(
                ['diff', '-Naur', str(self.project_path), str(self.shadow_path)],
                capture_output=True,
                text=True,
                timeout=30
            )

            # diff returns 1 if files differ, 0 if same, 2 on error
            if result.returncode == 2:
                raise ShadowWorkspaceError(f"diff command failed: {result.stderr}")

            return result.stdout

        except subprocess.TimeoutExpired:
            raise ShadowWorkspaceError("diff command timed out")
        except Exception as e:
            raise ShadowWorkspaceError(f"Failed to generate diff: {e}")

    def commit_to_main(self) -> bool:
        """
        Copy verified changes back to main workspace.
        Only call after verify_all passes.

        Returns:
            True if commit successful
        """
        if not self._created:
            raise ShadowWorkspaceError("Shadow workspace not created")

        logger.warning("Committing shadow changes to main workspace")

        try:
            # Copy files from shadow to main
            for item in self.shadow_path.iterdir():
                if item.name.startswith('.shadow_'):
                    continue  # Skip internal shadow files

                src = self.shadow_path / item.name
                dst = self.project_path / item.name

                if src.is_dir():
                    if dst.exists():
                        shutil.rmtree(dst)
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)

            logger.info("Successfully committed changes to main workspace")
            return True

        except Exception as e:
            logger.error(f"Failed to commit changes: {e}")
            return False

    def destroy(self):
        """Clean up container and temp files."""
        if not self._created:
            return

        logger.info("Destroying shadow workspace")

        # Stop and remove container
        if self.container:
            try:
                self.container.stop(timeout=5)
                self.container.remove()
                logger.info(f"Removed container {self.container.id[:12]}")
            except Exception as e:
                logger.error(f"Failed to remove container: {e}")

        # Remove shadow directory
        if self.shadow_path and self.shadow_path.exists():
            try:
                shutil.rmtree(self.shadow_path)
                logger.info(f"Removed shadow directory {self.shadow_path}")
            except Exception as e:
                logger.error(f"Failed to remove shadow directory: {e}")

        self._created = False
        self.container = None
        self.shadow_path = None

    def __enter__(self):
        """Context manager entry."""
        self.create()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.destroy()
        return False


# Usage example
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Example usage
    with ShadowWorkspace('/path/to/project') as shadow:
        # Make changes
        shadow.write_file('main.py', '''
def greet(name: str) -> str:
    """Greet someone."""
    return f"Hello, {name}!"

if __name__ == "__main__":
    print(greet("World"))
''')

        # Verify changes
        results = shadow.verify_all()

        # Check results
        all_passed = all(
            r.status == VerificationResult.PASS
            for r in results.values()
        )

        if all_passed:
            print("All checks passed!")
            diff = shadow.get_diff()
            print(f"\nDiff:\n{diff}")

            # Commit if desired
            # shadow.commit_to_main()
        else:
            print("Some checks failed:")
            for check_name, report in results.items():
                if report.status != VerificationResult.PASS:
                    print(f"\n{check_name}:")
                    for diagnostic in report.diagnostics:
                        print(f"  {diagnostic.file}:{diagnostic.line}: {diagnostic.message}")
