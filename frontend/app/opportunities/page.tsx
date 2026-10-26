import { redirect } from "next/navigation";

/** The opportunity list is the dashboard's "For you" tab; older alert emails link here. */
export default function OpportunitiesPage() {
  redirect("/dashboard");
}
