package reader

// PageData is one comic page with raw image bytes (PNG or JPEG).
type PageData struct {
	Index int
	Name  string
	Data  []byte
}
