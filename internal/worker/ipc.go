package worker

import (
	"bufio"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"os/exec"
	"path/filepath"
	"sync"
)

// AnalyzeRequest is sent to ml_worker on stdin (one JSON line).
type AnalyzeRequest struct {
	ImageB64         string `json:"image_b64"`
	PageNum          int    `json:"page_num"`
	GlobalOrderStart int    `json:"global_order_start"`
	OutputDir        string `json:"output_dir"`
	UseSAM           bool   `json:"use_sam"`
	ReadingOrder     bool   `json:"reading_order"`
	RTL              bool   `json:"rtl"`
}

// PanelJSON mirrors Python worker panel fields.
type PanelJSON struct {
	PanelID      string      `json:"panel_id"`
	Bbox         []int       `json:"bbox"`
	Polygon      [][]int     `json:"polygon"`
	Confidence   float64     `json:"confidence"`
	ReadingOrder *int        `json:"reading_order"`
	Source       string      `json:"source"`
}

// AnalyzeResponse is one line from ml_worker stdout.
type AnalyzeResponse struct {
	Panels  []PanelJSON `json:"panels"`
	Files   []string    `json:"files"`
	TimeMS  float64     `json:"time_ms"`
	Error   *string     `json:"error"`
}

// PythonWorker runs persistent ml_worker/main.py subprocess.
type PythonWorker struct {
	cmd    *exec.Cmd
	stdin  io.WriteCloser
	stdout *bufio.Scanner
	mu     sync.Mutex
}

// NewPythonWorker starts python ml_worker/main.py from project root.
func NewPythonWorker(projectRoot, pythonExe string) (*PythonWorker, error) {
	script := filepath.Join(projectRoot, "ml_worker", "main.py")
	cmd := exec.Command(pythonExe, script)
	cmd.Dir = projectRoot
	stdin, err := cmd.StdinPipe()
	if err != nil {
		return nil, err
	}
	stdoutPipe, err := cmd.StdoutPipe()
	if err != nil {
		return nil, err
	}
	if err := cmd.Start(); err != nil {
		return nil, err
	}
	w := &PythonWorker{
		cmd:    cmd,
		stdin:  stdin,
		stdout: bufio.NewScanner(stdoutPipe),
	}
	return w, nil
}

// Analyze sends one page to the worker.
func (w *PythonWorker) Analyze(req AnalyzeRequest) (*AnalyzeResponse, error) {
	w.mu.Lock()
	defer w.mu.Unlock()

	body, err := json.Marshal(req)
	if err != nil {
		return nil, err
	}
	if _, err := fmt.Fprintf(w.stdin, "%s\n", body); err != nil {
		return nil, err
	}
	if !w.stdout.Scan() {
		return nil, fmt.Errorf("worker stdout closed: %w", w.stdout.Err())
	}
	var resp AnalyzeResponse
	if err := json.Unmarshal(w.stdout.Bytes(), &resp); err != nil {
		return nil, err
	}
	if resp.Error != nil && *resp.Error != "" {
		return &resp, fmt.Errorf("worker error: %s", *resp.Error)
	}
	return &resp, nil
}

// Close terminates the worker process.
func (w *PythonWorker) Close() error {
	_ = w.stdin.Close()
	return w.cmd.Wait()
}

// EncodeImageB64 encodes raw image bytes for IPC.
func EncodeImageB64(data []byte) string {
	return base64.StdEncoding.EncodeToString(data)
}
