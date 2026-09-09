import type { TransportOfficeRow } from "../../types/transportAnalysis";
import { useTheme } from "../../context/ThemeContext";
import { formatNumber } from "../../styles/theme";

type Props = {
  offices: TransportOfficeRow[];
  highlightOverages?: boolean;
};

function isOverageOffice(office: TransportOfficeRow) {
  return office.status === "WARNING" || (office.difference ?? 0) > 0;
}

function statusLabel(office: TransportOfficeRow) {
  if (office.statusLabel) return office.statusLabel;
  const overage = isOverageOffice(office);
  const delayed = Boolean(office.delayed);
  if (overage && delayed) return "초과/지연";
  if (overage) return "초과";
  if (delayed) return "지연";
  return "정상";
}

function statusColor(label: string, palette: ReturnType<typeof useTheme>["palette"]) {
  if (label.includes("초과") || label.includes("지연")) return palette.warning;
  return palette.normal;
}

export function TransportOfficeTable({ offices, highlightOverages = false }: Props) {
  const { palette } = useTheme();

  if (!offices.length) {
    return <div style={{ color: palette.muted, fontSize: 13 }}>집중국 운송 데이터가 없습니다.</div>;
  }

  return (
    <div className="imc-table-scroll">
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
        <thead style={{ position: "sticky", top: 0, background: palette.panel, zIndex: 1 }}>
          <tr style={{ color: palette.muted, textAlign: "left", borderBottom: `1px solid ${palette.border}` }}>
            <th style={{ padding: "10px 8px" }}>집중국</th>
            <th style={{ padding: "10px 8px", textAlign: "right" }}>물량</th>
            <th style={{ padding: "10px 8px", textAlign: "center" }}>차량수</th>
            <th style={{ padding: "10px 8px", textAlign: "center" }}>쿼터</th>
            <th style={{ padding: "10px 8px", textAlign: "center" }}>초과/미달</th>
            <th style={{ padding: "10px 8px", textAlign: "center" }}>최종도착</th>
            <th style={{ padding: "10px 8px", textAlign: "center" }}>상태</th>
          </tr>
        </thead>
        <tbody>
          {offices.map((office) => {
            const overage = isOverageOffice(office);
            const label = statusLabel(office);
            const rowStyle =
              highlightOverages && overage
                ? { background: "rgba(234, 179, 8, 0.12)" }
                : undefined;

            return (
              <tr key={office.office} style={rowStyle}>
                <td style={{ padding: "10px 8px", fontWeight: overage ? 600 : 400 }}>{office.office}</td>
                <td style={{ padding: "10px 8px", textAlign: "right" }}>{formatNumber(office.volume)}</td>
                <td style={{ padding: "10px 8px", textAlign: "center" }}>{office.vehiclesActual ?? "-"}</td>
                <td style={{ padding: "10px 8px", textAlign: "center" }}>{office.vehiclesQuota ?? "-"}</td>
                <td
                  style={{
                    padding: "10px 8px",
                    textAlign: "center",
                    color: (office.difference ?? 0) > 0 ? palette.warning : palette.text,
                  }}
                >
                  {office.difference ?? "-"}
                </td>
                <td style={{ padding: "10px 8px", textAlign: "center" }}>{office.arrivalTime ?? "-"}</td>
                <td style={{ padding: "10px 8px", textAlign: "center", color: statusColor(label, palette) }}>
                  {label}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
