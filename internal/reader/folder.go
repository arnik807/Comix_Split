package reader

import (
	"os"
	"path/filepath"
	"sort"
	"strings"
)

// ReadFolder reads supported images from a directory (non-recursive).
func ReadFolder(dirPath string) ([]PageData, error) {
	entries, err := os.ReadDir(dirPath)
	if err != nil {
		return nil, err
	}
	var names []string
	for _, e := range entries {
		if e.IsDir() {
			continue
		}
		ext := strings.ToLower(filepath.Ext(e.Name()))
		if imageExts[ext] {
			names = append(names, e.Name())
		}
	}
	sort.Strings(names)

	pages := make([]PageData, 0, len(names))
	for i, name := range names {
		full := filepath.Join(dirPath, name)
		data, err := os.ReadFile(full)
		if err != nil {
			return nil, err
		}
		pages = append(pages, PageData{
			Index: i + 1,
			Name:  name,
			Data:  data,
		})
	}
	return pages, nil
}
