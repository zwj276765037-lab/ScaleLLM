# Current final design

The public architecture and numeric boundaries are documented in
[HARDWARE_ARCHITECTURE.md](../../../../docs/HARDWARE_ARCHITECTURE.md).
The register/descriptor contract is [abi.json](abi.json). Source identities are
in [hardware_source_manifest.json](../../../../deploy/final/hardware_source_manifest.json).
This release preserves the reader011 RTL, ROM and XDC bytes. The portable build
scripts adapt project/output/tool paths while preserving clocks and IP settings.
