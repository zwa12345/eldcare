#!/bin/bash
# 中继下载脚本 - 使用 wget 分片下载
URL="$1"
LOCAL_PATH="$2"
NUM_THREADS=4

# 获取文件大小
FILE_SIZE=$(curl -sI "$URL" | grep -i content-length | awk '{print $2}')
echo "文件大小: $FILE_SIZE bytes ($((FILE_SIZE/1024/1024)) MB)"

CHUNK_SIZE=$((FILE_SIZE / NUM_THREADS))

# 创建空文件
> "$LOCAL_PATH"

# 下载分片
for i in $(seq 0 $((NUM_THREADS-1))); do
    START=$((i * CHUNK_SIZE))
    if [ $i -eq $((NUM_THREADS-1)) ]; then
        END=$((FILE_SIZE - 1))
    else
        END=$((START + CHUNK_SIZE - 1))
    fi
    
    echo "Thread $i: $START-$END"
    wget -q -O "${LOCAL_PATH}.part${i}" --header="Range: bytes=${START}-${END}" "$URL" &
done

# 等待所有下载完成
wait

# 合并分片
echo "合并分片..."
> "$LOCAL_PATH"
for i in $(seq 0 $((NUM_THREADS-1))); do
    cat "${LOCAL_PATH}.part${i}" >> "$LOCAL_PATH"
    rm -f "${LOCAL_PATH}.part${i}"
done

echo "完成: $(ls -lh "$LOCAL_PATH")"
