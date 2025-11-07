# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.5.0] - 03-10-2025

### Added

- Event logging for SMS sent and changes found.

### Changed

- Bumped OpenOrchestrator to 2.*

## [1.4.0] - 19-06-2025

### Added

- List of SMS sent with a count added to email for statistics.

## [1.3.0] - 19-06-2025

### Added

- Robot now sends out an SMS if a change or a new citizen at unknown address is found.

### Changed

- Refactored by moving some data from dict to dataclass.

## [1.2.2]

### Fixed

- Updated serviceplatformen to v3.

## [1.2.1]

### Fixed

- Reorganized checks and updates to OpenOechestrator queue, and added a check to not fail on null data from queue rows.

## [1.2.0]

### Added

- New entries from Datawarehouse will now be added to output if they are registered for Digital Post or NemSMS.

## [1.1.0]

### Changed

- Certificate is now retrieved from the Keyvault.
- Robot is now pointed at real Digital Post service.

## [1.0.0]

- Initial release

[1.3.0]: https://github.com/itk-dev-rpa/digital-post-ukendt-adresse/tag/1.3.0
[1.2.2]: https://github.com/itk-dev-rpa/digital-post-ukendt-adresse/tag/1.2.2
[1.2.1]: https://github.com/itk-dev-rpa/digital-post-ukendt-adresse/tag/1.2.1
[1.2.0]: https://github.com/itk-dev-rpa/digital-post-ukendt-adresse/tag/1.2.0
[1.1.0]: https://github.com/itk-dev-rpa/digital-post-ukendt-adresse/tag/1.1.0
[1.0.0]: https://github.com/itk-dev-rpa/digital-post-ukendt-adresse/tag/1.0.0
