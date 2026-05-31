package reader

import (
	"archive/zip"
	"io"
	"path"
	"path/filepath"
	"sort"
	"strings"
)

var imageExts = map[string]bool{
	".png": true, ".jpg": true, ".jpeg": true, ".bmp": true, ".tiff": true,
}

// ReadCBZ opens a CBZ/ZIP archive and returns pages in lexical order.
func ReadCBZ(filePath string) ([]PageData, error) {
	r, err := zip.OpenReader(filePath)
	if err != nil {
		return nil, err
	}
	defer r.Close()

	type item struct {
		name string
		file *zip.File
	}
	var items []item
	for _, f := range r.File {
		ext := strings.ToLower(filepath.Ext(f.Name))
		if imageExts[ext] {
			items = append(items, item{name: f.Name, file: f})
		}
	}
	sort.Slice(items, func(i, j int) bool {
		return items[i].name < items[j].name
	})

	pages := make([]PageData, 0, len(items))
	for i, it := range items {
		rc, err := it.file.Open()
		if err != nil {
			return nil, err
		}
		data, err := io.ReadAll(rc)
		rc.Close()
		if err != nil {
			return nil, err
		}
		pages = append(pages, PageData{
			Index: i + 1,
			Name:  path.Base(it.name),
			Data:  data,
		})
	}
	return pages, nil
}
