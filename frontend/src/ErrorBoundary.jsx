import React, { Component } from "react";


export class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error("Frontend render failed", error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <main className="boot-error">
          <h1>Colruyt Megha Setu (CMS)</h1>
          <p>Enterprise AI-Driven Self-Service Private Cloud Platform</p>
          <p>The frontend failed to render.</p>
          <pre>{this.state.error.message}</pre>
        </main>
      );
    }

    return this.props.children;
  }
}
