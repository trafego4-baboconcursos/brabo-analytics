from __future__ import annotations

from pathlib import Path
from typing import Iterable


def resolve_csv(directory: Path | str, canonical_name: str, aliases: Iterable[str] = ()) -> Path:
    """Return the first existing CSV path among the canonical name and aliases.

    The canonical file should be preferred by new scripts. Aliases keep older
    pipelines working while the workspace is being normalized.
    """
    base_path = Path(directory)
    for name in (canonical_name, *aliases):
        candidate = base_path / name
        if candidate.exists():
            return candidate
    searched = [canonical_name, *aliases]
    raise FileNotFoundError(f"CSV not found in {base_path}: {searched}")


def resolve_campaign_csv(base_path: Path | str, folder: str, canonical_name: str, aliases: Iterable[str] = ()) -> Path:
    """Resolve a CSV under a campaign folder.

    Parameters
    ----------
    base_path:
        Workspace root or analysis root.
    folder:
        Relative campaign folder, like '[PBB-FEV-26]/vendas'.
    canonical_name:
        Preferred standardized file name.
    aliases:
        Legacy names kept for compatibility.
    """
    return resolve_csv(Path(base_path) / folder, canonical_name, aliases)
