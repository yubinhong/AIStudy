"""Shared, byte-precise limits for private curriculum documents."""

# The product limit is 50 MiB, not 50 decimal megabytes. Keeping the value in
# one module prevents the browser, API upload boundary, private storage adapter,
# and parser worker from quietly using different limits.
MAX_DOCUMENT_BYTES = 50 * 1024 * 1024
MAX_TOTAL_DOCUMENT_BYTES = 4 * MAX_DOCUMENT_BYTES
