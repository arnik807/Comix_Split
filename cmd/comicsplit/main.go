package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"comicsplit/internal/export"
	"comicsplit/internal/reader"
	"comicsplit/internal/worker"
)

func main() {
	input := flag.String("input", "", "CBZ, ZIP, folder, or image path")
	output := flag.String("output", "./panels", "Output directory")
	workers := flag.Int("workers", 1, "Parallel Python workers (experimental)")
	useSAM := flag.Bool("sam", false, "Use MobileSAM (accurate mode)")
	readingOrder := flag.Bool("order", true, "Sort panels by reading order")
	rtl := flag.Bool("rtl", false, "Right-to-left reading order")
	python := flag.String("python", "", "Python executable (default: python)")
	flag.Parse()

	if *input == "" {
		fmt.Fprintf(os.Stderr, "Usage: comicsplit --input <path> --output <dir>\n")
		flag.PrintDefaults()
		os.Exit(2)
	}

	projectRoot, err := os.Getwd()
	if err != nil {
		fatal(err)
	}
	py := *python
	if py == "" {
		py = "python"
	}

	pages, err := reader.Load(*input)
	if err != nil {
		if os.IsNotExist(err) {
			abs, _ := filepath.Abs(*input)
			fatal(fmt.Errorf(
				"не найден: %s\n  (полный путь: %s)\n"+
					"Укажите существующий .cbz/.zip, папку (exam_imgs) или .jpg.\n"+
					"Пример: --input exam_imgs  или  --input test_page.jpg",
				*input, abs,
			))
		}
		fatal(err)
	}
	if len(pages) == 0 {
		fatal(fmt.Errorf("no pages found in %s", *input))
	}

	baseName := filepath.Base(*input)
	if ext := filepath.Ext(baseName); ext != "" {
		baseName = baseName[:len(baseName)-len(ext)]
	}
	outDir := filepath.Join(*output, baseName)
	if err := export.EnsureDir(outDir); err != nil {
		fatal(err)
	}

	n := *workers
	if n < 1 {
		n = 1
	}
	fmt.Printf("Processing %d pages (%d worker(s))…\n", len(pages), n)

	pool, err := worker.NewPool(n, projectRoot, py)
	if err != nil {
		fatal(err)
	}
	defer pool.Close()

	jobs := make([]worker.PageJob, len(pages))
	for i, p := range pages {
		jobs[i] = worker.PageJob{
			Page:         p,
			OutputDir:    outDir,
			UseSAM:       *useSAM,
			ReadingOrder: *readingOrder,
			RTL:          *rtl,
		}
	}

	results := pool.ProcessPagesSequential(jobs)
	totalPanels := 0
	for _, r := range results {
		if r.Err != nil {
			fmt.Fprintf(os.Stderr, "  page %03d: error: %v\n", r.PageIndex, r.Err)
			continue
		}
		totalPanels += r.PanelCount
		fmt.Printf("  page %03d: %d panels, %.0f ms\n", r.PageIndex, r.PanelCount, r.TimeMS)
	}

	fmt.Printf("Done: %d pages, %d panels → %s\n", len(pages), totalPanels, outDir)
}

func fatal(err error) {
	fmt.Fprintf(os.Stderr, "error: %v\n", err)
	os.Exit(1)
}
