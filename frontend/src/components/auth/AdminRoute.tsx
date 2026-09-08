import type { ReactNode } from "react";
import { useAdminAuth } from "../../context/AdminAuthContext";
import { AdminLoginPanel } from "./AdminLoginPanel";

type Props = {
  title: string;
  description?: string;
  children: ReactNode;
};

export function AdminRoute({ title, description, children }: Props) {
  const { isAdmin } = useAdminAuth();

  if (!isAdmin) {
    return <AdminLoginPanel title={title} description={description} />;
  }

  return <>{children}</>;
}
