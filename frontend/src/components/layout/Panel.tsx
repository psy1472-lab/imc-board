import type { CSSProperties, ReactNode } from "react";
import { useTheme } from "../../context/ThemeContext";
import { panelStyle } from "../../styles/panel";

type Props = {
  title?: string;
  actions?: ReactNode;
  children: ReactNode;
  style?: CSSProperties;
  className?: string;
};

export function Panel({ title, actions, children, style, className }: Props) {
  const { palette } = useTheme();
  return (
    <div className={className} style={{ ...panelStyle(palette), ...style }}>
      {title || actions ? (
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: 12,
            marginBottom: 12,
            flexWrap: "wrap",
          }}
        >
          {title ? <h3 style={{ margin: 0 }}>{title}</h3> : <span />}
          {actions}
        </div>
      ) : null}
      {children}
    </div>
  );
}
