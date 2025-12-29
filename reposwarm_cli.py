#!/usr/bin/env python3
"""
RepoSwarm CLI for GitHub Actions
Simplified version that bypasses Temporal workflows for CI/CD use.

Usage:
    python reposwarm_cli.py analyze-all --config prompts/repos.json --output-dir ./temp
    python reposwarm_cli.py analyze-one --repo-url https://github.com/user/repo --repo-type backend
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Optional, Dict, Any
import os
import subprocess
import shutil


class SimpleInvestigator:
    """Simplified investigator that uses Claude SDK directly."""
    
    def __init__(self, anthropic_api_key: str):
        self.api_key = anthropic_api_key
        
    async def analyze_repository(
        self,
        repo_url: str,
        repo_type: str,
        output_dir: Path,
        cache_dir: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Analyze a single repository using Claude.
        
        Returns dict with:
        - success: bool
        - repo_name: str
        - output_file: Path
        - error: Optional[str]
        """
        repo_name = repo_url.split('/')[-1].replace('.git', '')
        output_file = output_dir / f"{repo_name}.arch.md"
        
        print(f"\n{'='*60}")
        print(f"🔍 Analyzing: {repo_name}")
        print(f"📦 Type: {repo_type}")
        print(f"🔗 URL: {repo_url}")
        print(f"{'='*60}\n")
        
        # Create temp clone directory
        clone_dir = output_dir / f"clone_{repo_name}"
        clone_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Clone repository
            print(f"📥 Cloning repository...")
            result = subprocess.run(
                ["git", "clone", "--depth=1", repo_url, str(clone_dir)],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode != 0:
                raise Exception(f"Git clone failed: {result.stderr}")
            
            print(f"✅ Repository cloned")
            
            # Load prompts for this repo type
            prompts_dir = Path("prompts") / repo_type
            if not prompts_dir.exists():
                prompts_dir = Path("prompts") / "shared"
            
            prompts_file = prompts_dir / "prompts.json"
            
            if prompts_file.exists():
                with open(prompts_file) as f:
                    prompts_config = json.load(f)
                print(f"📝 Loaded {len(prompts_config.get('prompts', []))} prompts")
            else:
                prompts_config = {"prompts": []}
            
            # Generate architecture doc using Claude
            print(f"🤖 Generating architecture analysis...")
            
            # Build file tree
            file_tree = self._build_file_tree(clone_dir)
            
            # Read key files
            key_files = self._read_key_files(clone_dir)
            
            # Call Claude API
            arch_doc = await self._call_claude_api(
                repo_name=repo_name,
                repo_type=repo_type,
                file_tree=file_tree,
                key_files=key_files,
                prompts=prompts_config.get('prompts', [])
            )
            
            # Write output
            output_file.write_text(arch_doc)
            print(f"✅ Generated: {output_file}")
            
            return {
                "success": True,
                "repo_name": repo_name,
                "output_file": output_file,
                "error": None
            }
            
        except Exception as e:
            print(f"❌ Error: {e}")
            return {
                "success": False,
                "repo_name": repo_name,
                "output_file": None,
                "error": str(e)
            }
        
        finally:
            # Cleanup clone directory
            if clone_dir.exists():
                shutil.rmtree(clone_dir, ignore_errors=True)
    
    def _build_file_tree(self, repo_dir: Path, max_depth: int = 3) -> str:
        """Build a tree representation of repository structure."""
        lines = []
        
        def walk_dir(path: Path, prefix: str = "", depth: int = 0):
            if depth > max_depth:
                return
            
            try:
                items = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name))
                for i, item in enumerate(items):
                    # Skip common ignored directories
                    if item.name in ['.git', 'node_modules', '__pycache__', 'venv', '.venv', 'dist', 'build']:
                        continue
                    
                    is_last = i == len(items) - 1
                    current_prefix = "└── " if is_last else "├── "
                    next_prefix = "    " if is_last else "│   "
                    
                    lines.append(f"{prefix}{current_prefix}{item.name}")
                    
                    if item.is_dir():
                        walk_dir(item, prefix + next_prefix, depth + 1)
            except PermissionError:
                pass
        
        walk_dir(repo_dir)
        return "\n".join(lines)
    
    def _read_key_files(self, repo_dir: Path) -> Dict[str, str]:
        """Read key configuration files."""
        key_files = {}
        
        common_files = [
            'README.md',
            'package.json',
            'requirements.txt',
            'pyproject.toml',
            'Cargo.toml',
            '.github/workflows/*.yml',
            '.github/workflows/*.yaml'
        ]
        
        for pattern in common_files:
            if '*' in pattern:
                # Handle wildcards
                parent = repo_dir / Path(pattern).parent
                if parent.exists():
                    for file in parent.glob(Path(pattern).name):
                        try:
                            key_files[str(file.relative_to(repo_dir))] = file.read_text()[:5000]  # Limit to 5KB
                        except:
                            pass
            else:
                file_path = repo_dir / pattern
                if file_path.exists():
                    try:
                        key_files[pattern] = file_path.read_text()[:5000]  # Limit to 5KB
                    except:
                        pass
        
        return key_files
    
    async def _call_claude_api(
        self,
        repo_name: str,
        repo_type: str,
        file_tree: str,
        key_files: Dict[str, str],
        prompts: list
    ) -> str:
        """Call Claude API to generate architecture documentation."""
        
        # Build prompt
        prompt_parts = [
            f"# Architecture Analysis for {repo_name}",
            f"\nRepository Type: {repo_type}",
            f"\n## File Structure\n```\n{file_tree}\n```",
        ]
        
        if key_files:
            prompt_parts.append("\n## Key Files")
            for filename, content in key_files.items():
                prompt_parts.append(f"\n### {filename}\n```\n{content}\n```")
        
        prompt_parts.append("\n## Analysis Request")
        prompt_parts.append("Generate comprehensive architecture documentation covering:")
        prompt_parts.append("1. System Overview")
        prompt_parts.append("2. Key Components")
        prompt_parts.append("3. Data Flow")
        prompt_parts.append("4. Technology Stack")
        prompt_parts.append("5. Deployment Architecture")
        prompt_parts.append("6. Security Considerations")
        
        if prompts:
            prompt_parts.append("\n## Specific Investigation Points")
            for prompt in prompts[:5]:  # Limit to 5 prompts
                prompt_parts.append(f"- {prompt.get('description', prompt.get('name', 'Unknown'))}")
        
        full_prompt = "\n".join(prompt_parts)
        
        # Call Claude API using curl (simpler than installing anthropic SDK)
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 4000,
                "messages": [
                    {
                        "role": "user",
                        "content": full_prompt
                    }
                ]
            }, f)
            request_file = f.name
        
        try:
            result = subprocess.run([
                'curl', '-X', 'POST',
                'https://api.anthropic.com/v1/messages',
                '-H', f'x-api-key: {self.api_key}',
                '-H', 'anthropic-version: 2023-06-01',
                '-H', 'content-type: application/json',
                '-d', f'@{request_file}'
            ], capture_output=True, text=True, timeout=120)
            
            response_data = json.loads(result.stdout)
            
            if 'content' in response_data and len(response_data['content']) > 0:
                return response_data['content'][0]['text']
            else:
                raise Exception(f"Claude API error: {response_data}")
        
        finally:
            Path(request_file).unlink(missing_ok=True)


async def analyze_all_repositories(
    config_path: Path,
    output_dir: Path,
    anthropic_api_key: str
) -> None:
    """Analyze all repositories from config file."""
    
    # Load config
    print(f"📋 Loading configuration from {config_path}")
    with open(config_path) as f:
        config = json.load(f)
    
    repos = config.get("repositories", {})
    print(f"📦 Found {len(repos)} repositories to analyze\n")
    
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize investigator
    investigator = SimpleInvestigator(anthropic_api_key)
    
    # Track results
    results = []
    
    # Analyze each repository
    for repo_name, repo_config in repos.items():
        result = await investigator.analyze_repository(
            repo_url=repo_config["url"],
            repo_type=repo_config["type"],
            output_dir=output_dir
        )
        results.append(result)
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"📊 ANALYSIS SUMMARY")
    print(f"{'='*60}")
    successful = sum(1 for r in results if r['success'])
    failed = len(results) - successful
    print(f"✅ Successful: {successful}/{len(results)}")
    if failed > 0:
        print(f"❌ Failed: {failed}/{len(results)}")
        for result in results:
            if not result['success']:
                print(f"   - {result['repo_name']}: {result['error']}")
    print(f"{'='*60}\n")


async def analyze_one_repository(
    repo_url: str,
    repo_type: str,
    output_dir: Path,
    anthropic_api_key: str
) -> None:
    """Analyze a single repository."""
    
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize investigator
    investigator = SimpleInvestigator(anthropic_api_key)
    
    # Analyze
    result = await investigator.analyze_repository(
        repo_url=repo_url,
        repo_type=repo_type,
        output_dir=output_dir
    )
    
    if not result['success']:
        sys.exit(1)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="RepoSwarm CLI for GitHub Actions",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest='command', required=True)
    
    # analyze-all command
    parser_all = subparsers.add_parser('analyze-all', help='Analyze all repositories from config')
    parser_all.add_argument('--config', type=Path, default=Path('prompts/repos.json'),
                           help='Path to repos.json configuration file')
    parser_all.add_argument('--output-dir', type=Path, default=Path('./temp'),
                           help='Output directory for .arch.md files')
    
    # analyze-one command
    parser_one = subparsers.add_parser('analyze-one', help='Analyze a single repository')
    parser_one.add_argument('--repo-url', type=str, required=True,
                           help='Repository URL (https://github.com/user/repo)')
    parser_one.add_argument('--repo-type', type=str, required=True,
                           choices=['backend', 'frontend', 'mobile', 'libraries', 'infra-as-code', 'shared'],
                           help='Repository type')
    parser_one.add_argument('--output-dir', type=Path, default=Path('./temp'),
                           help='Output directory for .arch.md files')
    
    args = parser.parse_args()
    
    # Get API key from environment
    anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
    if not anthropic_api_key:
        print("❌ Error: ANTHROPIC_API_KEY environment variable not set")
        sys.exit(1)
    
    # Execute command
    if args.command == 'analyze-all':
        asyncio.run(analyze_all_repositories(
            config_path=args.config,
            output_dir=args.output_dir,
            anthropic_api_key=anthropic_api_key
        ))
    
    elif args.command == 'analyze-one':
        asyncio.run(analyze_one_repository(
            repo_url=args.repo_url,
            repo_type=args.repo_type,
            output_dir=args.output_dir,
            anthropic_api_key=anthropic_api_key
        ))


if __name__ == "__main__":
    main()
