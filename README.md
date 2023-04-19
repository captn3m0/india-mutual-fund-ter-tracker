Indian Mutual Funds TER Tracker
-------------------------------

Tracks expense ratio changes for Indian Mutual Funds.
Watch the repository for any releases to get notified of any changes.

- `data.csv` holds the data. The Field headers are the same as https://www.amfiindia.com/ter-of-mf-schemes, with the exception of the TER Date field, which is dropped.
- You can directly access the latest version at <https://raw.githubusercontent.com/captn3m0/india-mutual-fund-ter-tracker/main/data.csv>.
- You can view the data online on GitHub at https://github.com/captn3m0/india-mutual-fund-ter-tracker/blob/main/data.csv

## Why

The emails sent by Mutual Funds are quite useless, as they don't contain the actual TER change, just a notification of the change.

Here's a sample notification for example:

![Sample TER change notification](https://user-images.githubusercontent.com/584253/232834205-d2ed106a-972f-49b0-9ced-8d5f031a9e59.png).

You're expected to go to the website, and find the TER details on your own.

This is a simple tracker that allows you to watch the TER changes for all funds.

## Get Notified 

You can follow these changes over:

1. Email by [Watching this repository for releases](http://web.archive.org/web/20181128151103/https://help.github.com/articles/watching-and-unwatching-releases-for-a-repository/).
2. RSS by subscribing to the [@tertracker@tatooine.club](https://tatooine.club/@tertracker.rss) RSS feed.
3. Fediverse by following [@tertracker@tatooine.club](https://tatooine.club/@tertracker) using your favorite app (Mastodon etc).

Note that the changelog only includes changes made to TER for Direct plans. Regular
plan TER changes are tracked, but not announced.

## Versioning

- New versions are tagged as `v1.YYYYDDD.k`, where `YYYYDDD` is the year and day of the year, and `k` is the hour of the day (That goes up to 24)
- This allows us to be compatible with Semver, and only bump major version in case of breaking changes in the schema.

## License

Licensed under the [MIT License](https://nemo.mit-license.org/). See LICENSE file for details.