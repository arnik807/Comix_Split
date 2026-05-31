package export

import (
	"os"
	"path/filepath"
)

// EnsureDir creates output directory if missing.
func EnsureDir(dir string) error {
	return os.MkdirAll(dir, 0o755)
}

// JoinOutput joins output dir and filename safely.
func JoinOutput(dir, filename string) string {
	return filepath.Join(dir, filename)
}
