package export

import "fmt"

// PanelFilename builds `{global:03d}_p{page:03d}_panel_{n:02d}.png` style names.
func PanelFilename(globalOrder, pageNum, panelNum int) string {
	return fmt.Sprintf("%03d_page_%03d_panel_%02d.png", globalOrder, pageNum, panelNum)
}
