# Public Scripts

The repository contains capture, analysis, recovery, research, safety, and test
utilities. Scripts operate on controlled local inputs and must not publish raw
private evidence.

## Documentation and public-repository gates

```bash
bash scripts/safety/validate_public_repo.sh
python3 scripts/safety/check_markdown_links.py --repo .
python3 scripts/safety/check_documentation_governance.py --repo .
```

The documentation-governance gate validates the audience navigation manifest,
page-status metadata, canonical-page coverage, unique titles, consumer
navigation boundary, and legacy forwarders.

See the subdirectory READMEs for capture, analysis, recovery, and research
usage.
