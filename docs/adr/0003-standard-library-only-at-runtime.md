# Standard library only at runtime

The tool is installed into environments we don't control, where each runtime dependency is a possible version conflict. We use `tomllib` (Python 3.11 and later) for config and `argparse` for the CLI, so no PyYAML, tomli or click is needed. Test dependencies are unrestricted. The cost is that anything the standard library lacks must be written by hand, and we reject YAML config because it would need PyYAML.
