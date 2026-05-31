package worker

import (
	"fmt"
	"sync"

	"comicsplit/internal/reader"
)

// PageJob is one page to analyze.
type PageJob struct {
	Page           reader.PageData
	GlobalStart    int
	OutputDir      string
	UseSAM         bool
	ReadingOrder   bool
	RTL            bool
}

// PageResult holds worker output for a page.
type PageResult struct {
	PageIndex   int
	PanelCount  int
	TimeMS      float64
	Err         error
}

// Pool processes pages with N parallel Python workers.
type Pool struct {
	workers []*PythonWorker
}

// NewPool creates n worker subprocesses.
func NewPool(n int, projectRoot, pythonExe string) (*Pool, error) {
	if n < 1 {
		n = 1
	}
	p := &Pool{}
	for i := 0; i < n; i++ {
		w, err := NewPythonWorker(projectRoot, pythonExe)
		if err != nil {
			for _, existing := range p.workers {
				_ = existing.Close()
			}
			return nil, fmt.Errorf("worker %d: %w", i, err)
		}
		p.workers = append(p.workers, w)
	}
	return p, nil
}

// ProcessPagesSequential processes pages in order for correct global panel numbering.
func (p *Pool) ProcessPagesSequential(jobs []PageJob) []PageResult {
	results := make([]PageResult, len(jobs))
	globalStart := 0
	w := p.workers[0]

	for i, job := range jobs {
		job.GlobalStart = globalStart
		req := AnalyzeRequest{
			ImageB64:         EncodeImageB64(job.Page.Data),
			PageNum:          job.Page.Index,
			GlobalOrderStart: globalStart,
			OutputDir:        job.OutputDir,
			UseSAM:           job.UseSAM,
			ReadingOrder:     job.ReadingOrder,
			RTL:              job.RTL,
		}
		resp, err := w.Analyze(req)
		pr := PageResult{PageIndex: job.Page.Index}
		if err != nil {
			pr.Err = err
		} else {
			pr.PanelCount = len(resp.Panels)
			pr.TimeMS = resp.TimeMS
			globalStart += pr.PanelCount
		}
		results[i] = pr
	}
	return results
}

// ProcessPagesParallel runs jobs in parallel (global order may overlap — use sequential for production).
func (p *Pool) ProcessPagesParallel(jobs []PageJob) []PageResult {
	results := make([]PageResult, len(jobs))
	var wg sync.WaitGroup
	var mu sync.Mutex
	nextWorker := 0

	for i, job := range jobs {
		wg.Add(1)
		go func(slot int, job PageJob) {
			defer wg.Done()
			mu.Lock()
			w := p.workers[nextWorker%len(p.workers)]
			nextWorker++
			mu.Unlock()

			req := AnalyzeRequest{
				ImageB64:         EncodeImageB64(job.Page.Data),
				PageNum:          job.Page.Index,
				GlobalOrderStart: job.GlobalStart,
				OutputDir:        job.OutputDir,
				UseSAM:           job.UseSAM,
				ReadingOrder:     job.ReadingOrder,
				RTL:              job.RTL,
			}
			resp, err := w.Analyze(req)
			pr := PageResult{PageIndex: job.Page.Index}
			if err != nil {
				pr.Err = err
			} else {
				pr.PanelCount = len(resp.Panels)
				pr.TimeMS = resp.TimeMS
			}
			mu.Lock()
			results[slot] = pr
			mu.Unlock()
		}(i, job)
	}
	wg.Wait()
	return results
}

// Close all workers.
func (p *Pool) Close() {
	for _, w := range p.workers {
		_ = w.Close()
	}
}
