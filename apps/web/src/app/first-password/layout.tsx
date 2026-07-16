import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { ReactNode } from "react";

export default async function FirstPasswordLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  if (!(await cookies()).get("study_session")) redirect("/login");
  return children;
}
