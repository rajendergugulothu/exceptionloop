import { SignIn } from "@clerk/nextjs";

export default function SignInPage() {
  return (
    <div style={{
      minHeight: "100vh",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      background: "var(--bg)",
    }}>
      <div style={{ textAlign: "center" }}>
        <div style={{ marginBottom: 32 }}>
          <div style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 10,
            marginBottom: 8,
          }}>
            <div style={{
              width: 36,
              height: 36,
              background: "var(--accent)",
              borderRadius: 9,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 15,
              fontWeight: 800,
              color: "#fff",
            }}>EL</div>
            <span style={{ fontSize: 20, fontWeight: 700, letterSpacing: "-0.3px" }}>ExceptionLoop</span>
          </div>
          <p style={{ fontSize: 13, color: "var(--text-2)" }}>Operational control plane for AI agent exceptions</p>
        </div>
        <SignIn />
      </div>
    </div>
  );
}
