import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--foo", default="bar")
args = parser.parse_args()

print(f"Demo OK: {args.foo}")
