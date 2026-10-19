export default function HomePage() {
  return (
    <main>
      <h1>OppRadar 📡</h1>
      <p>
        AI-powered radar for internships, jobs, scholarships and competitions.
        This is the scaffold — the real UI is on its way (owner: Riad).
      </p>
      <p>
        The API lives at{" "}
        <code>{process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}</code>
        .
      </p>
    </main>
  );
}
