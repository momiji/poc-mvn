# mvn dependencies analyzer

This is a tool to help analyze all maven dependencies, with the ability to understand where dependencies and versions are coming from.

This is of course a work in progress and is limited to my use case.

So far:

- [x] propreties with parents
- [x] dependencyManagement with parents
- [x] dependencies with parents
- [ ] profiles
- [ ] download missing pom

## Using

TODO

## Tests

You need to compile maven project to download all dependencies:

```bash
( cd myartifact ; mvn compile )
```

Then test:

```bash
python pom_printer.py
```
