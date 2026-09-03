# Increment 567 Notes — native Intel macOS desktop and Local AI

## Why

Callosum 0.5.3 made managed Local AI real on Apple Silicon, but the application and updater still had no Intel
macOS artifact. This matters immediately because all known external adopters use Macs, and an Intel user cannot
run an arm64-only application merely by accepting a slower Local AI configuration.

## Implementation

- The macOS workflow is now a two-architecture native matrix: `macos-latest` for arm64 and the current official
  `macos-15-intel` x86_64 runner. Each job builds its own portable Python/dependency tree, Rust/Tauri app,
  managed-runtime acceptance, `.dmg`, updater archive/signature, and mounted-app/Gatekeeper exercise.
- `build_python_macos.sh` selects the matching pinned python-build-standalone architecture from `uname -m` and
  fails on anything else. It does not build under Rosetta or relabel one architecture as another.
- Upstream PyTorch no longer publishes current releases for Intel macOS. The native x86_64 dependency lane
  therefore pins the last official Intel wheel (`torch==2.2.2`), its required NumPy 1.x ABI, and
  `transformers==4.57.6` (the current stack's last line supporting Torch 2.2). Other platforms retain the current
  dependency resolution. The packaged-runtime smoke test remains blocking.
- Because that legacy Intel wheel carries a critical advisory in PyTorch's pickle checkpoint loader, every
  Callosum-owned SentenceTransformer/CrossEncoder load now requires safetensors. The pinned production model
  revisions provide safetensors; missing safe weights fail closed instead of falling back to pickle.
- The managed installer selects llama.cpp b10516's official x64 macOS archive at compile time. The independently
  audited identities are archive bytes `11,395,897`, archive SHA-256
  `b7adecf7bd2cde577ddabee8357a72409165d8104f43b4acee9f1b98cc9c447a`, launcher SHA-256
  `f3136584b712d052374aa14765bea077721dc886af647228483ce79e2d838964`, and bundle-manifest SHA-256
  `9621e3a085f91d8c3091540c80684cde76dd637862fa0e07910744a8f63534f3`.
- Intel keeps the production Preview's explicit CPU execution (`--n-gpu-layers 0`). This increment does not
  invent an Intel GPU/Metal policy or change Automatic AI routing.
- Release assembly now keeps platform downloads in separate directories, stages uniquely named public assets,
  and requires both signed Mac updater archives before writing `latest.json`. The updater manifest includes
  distinct `darwin-aarch64` and `darwin-x86_64` entries plus stable arm64/x64 `.dmg` aliases.

## Security and identity boundary

Intel uses the same immutable-source, size/SHA-256, allowlisted tar-entry, safe-symlink, atomic-promotion,
strict-loopback, bearer-authenticated, requested-versus-observed, no-cloud-fallback, and process-group cleanup
invariants as Apple Silicon. Its runtime bundle has a separate identity; similarity of filenames or upstream
version is not treated as binary equivalence.

## Validation boundary

The workflow/YAML and packaging assertions pass locally. Windows Rust compilation was attempted from a clean
external Cargo target and reached the final Tauri crate without a compiler diagnostic, but the local Cargo
process again stalled during finalization in this Dropbox-backed checkout; it was stopped rather than claimed as
passing. Native Intel and Apple Silicon CI are release-blocking and must both pass before 0.5.4 is tagged.
