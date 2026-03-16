"""LunaClaw Brief — GitHub 数据源（含竞品对比）"""

from datetime import datetime

import aiohttp

from brief.models import Item
from brief.sources.base import BaseSource
from brief.registry import register_source


@register_source("github")
class GitHubSource(BaseSource):
    name = "github"

    SEARCH_QUERIES = [
        "computer vision", "OCR", "multimodal AI", "document AI",
        "image segmentation", "object detection", "vision transformer",
        "layout analysis", "text recognition", "document understanding",
    ]

    async def fetch(self, since: datetime, until: datetime) -> list[Item]:
        items: list[Item] = []
        seen_repos: set[str] = set()
        token = self.global_config.get("github", {}).get("token", "")
        headers = {"Accept": "application/vnd.github.v3+json"}
        if token:
            headers["Authorization"] = f"token {token}"

        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for query in self.SEARCH_QUERIES:
                try:
                    url = (
                        f"https://api.github.com/search/repositories"
                        f"?q={query}+language:python&sort=stars&order=desc&per_page=8"
                    )
                    async with session.get(url, headers=headers) as resp:
                        if resp.status != 200:
                            continue
                        data = await resp.json()
                        for repo in data.get("items", []):
                            repo_name = repo["full_name"]
                            if repo_name in seen_repos:
                                continue
                            seen_repos.add(repo_name)
                            stars = repo.get("stargazers_count", 0)
                            if stars < 50:
                                continue
                            desc = repo.get("description", "") or ""
                            topics = repo.get("topics", [])
                            items.append(Item(
                                title=repo_name,
                                url=repo["html_url"],
                                source="github",
                                raw_text=desc[:500],
                                published_at=repo.get("updated_at", ""),
                                meta={
                                    "stars": stars,
                                    "forks": repo.get("forks_count", 0),
                                    "language": repo.get("language", ""),
                                    "topics": topics,
                                },
                            ))
                except Exception:
                    continue

            # 按最近更新抓取热门
            try:
                date_str = since.strftime("%Y-%m-%d")
                url = (
                    f"https://api.github.com/search/repositories"
                    f"?q=computer+vision+OR+OCR+OR+multimodal+pushed:>{date_str}"
                    f"&sort=updated&order=desc&per_page=15"
                )
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        for repo in data.get("items", []):
                            repo_name = repo["full_name"]
                            if repo_name in seen_repos:
                                continue
                            seen_repos.add(repo_name)
                            desc = repo.get("description", "") or ""
                            items.append(Item(
                                title=repo_name,
                                url=repo["html_url"],
                                source="github",
                                raw_text=desc[:500],
                                published_at=repo.get("updated_at", ""),
                                meta={
                                    "stars": repo.get("stargazers_count", 0),
                                    "forks": repo.get("forks_count", 0),
                                    "language": repo.get("language", ""),
                                    "topics": repo.get("topics", []),
                                    "recently_updated": True,
                                },
                            ))
            except Exception:
                pass

            # 为 Top 项目查找竞品/替代方案
            top_items = sorted(items, key=lambda x: x.meta.get("stars", 0), reverse=True)[:8]
            for item in top_items:
                try:
                    alternatives = await self._find_alternatives(
                        session, headers, item, seen_repos
                    )
                    if alternatives:
                        item.meta["alternatives"] = alternatives
                except Exception:
                    pass

        return items

    async def _find_alternatives(
        self,
        session: aiohttp.ClientSession,
        headers: dict,
        item: Item,
        seen_repos: set[str],
    ) -> list[dict]:
        """通过 topics 和关键词查找竞品/替代方案"""
        topics = item.meta.get("topics", [])
        if not topics:
            words = item.title.split("/")[-1].lower().replace("-", " ").split()
            topics = [w for w in words if len(w) > 3][:3]

        if not topics:
            return []

        query = "+".join(topics[:3])
        url = (
            f"https://api.github.com/search/repositories"
            f"?q={query}&sort=stars&order=desc&per_page=5"
        )

        alternatives: list[dict] = []
        try:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                for repo in data.get("items", []):
                    repo_name = repo["full_name"]
                    if repo_name == item.title or repo_name in seen_repos:
                        continue
                    alternatives.append({
                        "name": repo_name,
                        "stars": repo.get("stargazers_count", 0),
                        "description": (repo.get("description", "") or "")[:200],
                        "url": repo["html_url"],
                        "language": repo.get("language", ""),
                    })
                    if len(alternatives) >= 3:
                        break
        except Exception:
            pass

        return alternatives
