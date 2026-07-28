import React from "react";

const FEATURES = [
  {
    title: "Shortest-time routing, not shortest-distance",
    body: "Real road-network routing powered by OSRM calculates the fastest path through Bangalore traffic, not just the shortest line on a map.",
  },
  {
    title: "Automatic traffic signal preemption",
    body: "As an ambulance approaches a junction, the system calculates exactly when the signal needs to turn green so standing traffic clears just before it arrives.",
  },
  {
    title: "Severity-based hospital selection",
    body: "Primary, secondary, and tertiary care hospitals are ranked by real travel time, matched to how critical the emergency is.",
  },
  {
    title: "Specialty matching from a text description",
    body: "Describe the emergency in plain language - eye injury, chest pain, a broken bone - and the system matches it to the right specialty hospital nearby: cardiology, orthopedic, ophthalmology, ENT, neurology, and more.",
  },
];

const STEPS = [
  "Set the ambulance's current location on the map",
  "Choose emergency severity, or describe the emergency in your own words",
  "The system finds the nearest matching hospital by real travel time",
  "Watch the route and traffic signals update live as the ambulance moves",
];

export default function LandingPage({ onSignIn, onSignUp }) {
  return (
    <div className="landing">
      <header className="landing-hero">
        <div className="landing-hero-inner">
          <h1>Bangalore Emergency Vehicle Routing System</h1>
          <p className="landing-subhead">
            AI-powered ambulance navigation with real-time traffic signal preemption and
            severity-based hospital routing - built for faster emergency response across Bangalore.
          </p>
          <div className="landing-cta-row">
            <button className="btn-primary landing-cta" onClick={onSignUp}>
              Get started
            </button>
            <button className="btn-ghost landing-cta" onClick={onSignIn}>
              Sign in
            </button>
          </div>
        </div>
      </header>

      <main>
        <section className="landing-section">
          <h2>What it does</h2>
          <div className="landing-features">
            {FEATURES.map((f) => (
              <article className="landing-feature-card" key={f.title}>
                <h3>{f.title}</h3>
                <p>{f.body}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="landing-section">
          <h2>How it works</h2>
          <ol className="landing-steps">
            {STEPS.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ol>
        </section>
      </main>

      <footer className="landing-footer">
        <p>Bangalore Emergency Vehicle Routing System - a real-time ambulance dispatch and traffic-signal-preemption demo.</p>
      </footer>
    </div>
  );
}
