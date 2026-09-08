import type { CSSProperties, ReactNode } from "react";
import { useTheme } from "../../context/ThemeContext";
import { panelStyle } from "../../styles/panel";

type Props = {
  title?: string;
  children: ReactNode;
  style?: CSSProperties;
  className?: string;
};

export function Panel({ title, children, style, className }: Props) {
  const { palette } = useTheme();
  return (
    <div className={className} style={{ ...panelStyle(palette), ...style }}>
      {title ? <h3 style={{ margin: "0 0 12px" }}>{title}</h3> : null}
      {children}
    </div>
  );
}
