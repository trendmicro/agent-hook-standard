# Agent Hook `image-size` patch

This directory vendors the MIT-licensed `image-size` 2.0.2 distribution until
the upstream package publishes a security fix. It is versioned as
`2.0.3-agent-hook.0` and is consumed only through the website's local npm
override.

The patch rejects malformed ICNS entries and ISO Base Media File Format boxes
whose declared length cannot advance parsing. This prevents the zero-length
ICNS, JXL, and HEIF parser loops tracked by CVE-2025-71330 and CVE-2025-71329.

Remove this fork and its override when a maintained upstream release is
available and has been reviewed.
