import sys

from requests import HTTPError, RequestException, Timeout

from indexer import build_index


def main() -> int:
    try:
        result = build_index(log=print)
    except RuntimeError as exc:
        print(f"初始化失败：{exc}")
        return 1
    except HTTPError as exc:
        print(f"Embedding API 请求失败：{exc}")
        return 1
    except Timeout:
        print("Embedding 请求超时：可以稍后重试。")
        return 1
    except RequestException as exc:
        print(f"Embedding 网络请求异常：{exc}")
        return 1
    except RuntimeError as exc:
        print(f"处理失败：{exc}")
        return 1

    print("\nQdrant 增量索引完成。")
    print(f"新增或更新文档数量：{len(result.changed_sources)}")
    print(f"跳过未变更文档数量：{len(result.skipped_sources)}")
    print(f"删除过期文档数量：{len(result.removed_sources)}")
    print(f"本次写入片段数量：{result.written_points}")
    print(f"collection：{result.collection_name}")
    print(f"storage：{result.storage_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
