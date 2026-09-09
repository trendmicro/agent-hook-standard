# Agent Hook Docusaurus MDX loader patch

This runtime-only copy of the MIT-licensed Docusaurus MDX loader preserves the
upstream package name and version for compatibility. Its only change is to
import the locally vendored `@agent-hook-spec/image-size` package instead of
the archived, vulnerable `image-size` package.

Remove this copy and the associated npm override when Docusaurus adopts a
maintained upstream image-dimension parser with an available security fix.
