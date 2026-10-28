// Command rb is the single ResultBench binary. Every component of the
// testbed is a subcommand, so one container image serves all designs.
package main

import (
	"fmt"
	"os"
	"sort"
)

type command struct {
	run   func(args []string) error
	brief string
}

var commands = map[string]command{
	"portal":      {runPortal, "serve results (designs A, B0-B3, C1)"},
	"waitingroom": {runWaitingRoom, "admission layer in front of a backend (design D)"},
	"dbload":      {runDBLoad, "generate the synthetic dataset and load it into PostgreSQL"},
	"materialize": {runMaterialize, "pre-compute results into Redis or static files (C1, C2, B3)"},
	"correct":     {runCorrect, "publish (or revert) the correction batch"},
	"release":     {runRelease, "create a release flag file at release time (for Nginx)"},
	"surge":       {runSurge, "run a result-day load scenario"},
	"calibrate":   {runCalibrate, "find a design's saturation point with step load"},
	"sample":      {runSample, "print sample records from the synthetic dataset"},
	"publish-csv": {runPublishCSV, "publish a board's results CSV as static files (result-in-a-box)"},
	"fetch":       {runFetch, "GET a URL and print the body (for collecting /stats inside the network)"},
}

func usage() {
	fmt.Fprintln(os.Stderr, "usage: rb <command> [flags]\n\ncommands:")
	names := make([]string, 0, len(commands))
	for n := range commands {
		names = append(names, n)
	}
	sort.Strings(names)
	for _, n := range names {
		fmt.Fprintf(os.Stderr, "  %-12s %s\n", n, commands[n].brief)
	}
	fmt.Fprintln(os.Stderr, "\nEvery flag can also be set with an environment variable RB_<FLAG>, e.g. RB_DSN.")
}

func main() {
	if len(os.Args) < 2 {
		usage()
		os.Exit(2)
	}
	c, ok := commands[os.Args[1]]
	if !ok {
		usage()
		os.Exit(2)
	}
	if err := c.run(os.Args[2:]); err != nil {
		fmt.Fprintf(os.Stderr, "rb %s: %v\n", os.Args[1], err)
		os.Exit(1)
	}
}
