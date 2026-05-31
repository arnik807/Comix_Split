package reader

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// Load dispatches by path type (CBZ/ZIP, folder, single image file).
func Load(sourcePath string) ([]PageData, error) {
	info, err := os.Stat(sourcePath)
	if err != nil {
		return nil, err
	}
	if info.IsDir() {
		return ReadFolder(sourcePath)
	}
	ext := strings.ToLower(filepath.Ext(sourcePath))
	switch ext {
	case ".cbz", ".zip":
		return ReadCBZ(sourcePath)
	case ".png", ".jpg", ".jpeg", ".bmp", ".tiff":
		data, err := os.ReadFile(sourcePath)
		if err != nil {
			return nil, err
		}
		return []PageData{{
			Index: 1,
			Name:  filepath.Base(sourcePath),
			Data:  data,
		}}, nil
	default:
		return nil, fmt.Errorf("unsupported source: %s", sourcePath)
	}
}
