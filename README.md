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

Dependency tests by comparing with maven:

```bash
./test-all.sh
./cmp1.sh
./cmp2.sh
./cmp3.sh
```

Unit tests:

```bash
python pom_loader.py
python pom_printer.py
python pom_reader.py
python pom_solver.py
python pom_struct.py
```
