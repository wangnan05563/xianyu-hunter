/*
   Licensed to the Apache Software Foundation (ASF) under one or more
   contributor license agreements.  See the NOTICE file distributed with
   this work for additional information regarding copyright ownership.
   The ASF licenses this file to You under the Apache License, Version 2.0
   (the "License"); you may not use this file except in compliance with
   the License.  You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
*/
var showControllersOnly = false;
var seriesFilter = "";
var filtersOnlySampleSeries = true;

/*
 * Add header in statistics table to group metrics by category
 * format
 *
 */
function summaryTableHeader(header) {
    var newRow = header.insertRow(-1);
    newRow.className = "tablesorter-no-sort";
    var cell = document.createElement('th');
    cell.setAttribute("data-sorter", false);
    cell.colSpan = 1;
    cell.innerHTML = "Requests";
    newRow.appendChild(cell);

    cell = document.createElement('th');
    cell.setAttribute("data-sorter", false);
    cell.colSpan = 3;
    cell.innerHTML = "Executions";
    newRow.appendChild(cell);

    cell = document.createElement('th');
    cell.setAttribute("data-sorter", false);
    cell.colSpan = 7;
    cell.innerHTML = "Response Times (ms)";
    newRow.appendChild(cell);

    cell = document.createElement('th');
    cell.setAttribute("data-sorter", false);
    cell.colSpan = 1;
    cell.innerHTML = "Throughput";
    newRow.appendChild(cell);

    cell = document.createElement('th');
    cell.setAttribute("data-sorter", false);
    cell.colSpan = 2;
    cell.innerHTML = "Network (KB/sec)";
    newRow.appendChild(cell);
}

/*
 * Populates the table identified by id parameter with the specified data and
 * format
 *
 */
function createTable(table, info, formatter, defaultSorts, seriesIndex, headerCreator) {
    var tableRef = table[0];

    // Create header and populate it with data.titles array
    var header = tableRef.createTHead();

    // Call callback is available
    if(headerCreator) {
        headerCreator(header);
    }

    var newRow = header.insertRow(-1);
    for (var index = 0; index < info.titles.length; index++) {
        var cell = document.createElement('th');
        cell.innerHTML = info.titles[index];
        newRow.appendChild(cell);
    }

    var tBody;

    // Create overall body if defined
    if(info.overall){
        tBody = document.createElement('tbody');
        tBody.className = "tablesorter-no-sort";
        tableRef.appendChild(tBody);
        var newRow = tBody.insertRow(-1);
        var data = info.overall.data;
        for(var index=0;index < data.length; index++){
            var cell = newRow.insertCell(-1);
            cell.innerHTML = formatter ? formatter(index, data[index]): data[index];
        }
    }

    // Create regular body
    tBody = document.createElement('tbody');
    tableRef.appendChild(tBody);

    var regexp;
    if(seriesFilter) {
        regexp = new RegExp(seriesFilter, 'i');
    }
    // Populate body with data.items array
    for(var index=0; index < info.items.length; index++){
        var item = info.items[index];
        if((!regexp || filtersOnlySampleSeries && !info.supportsControllersDiscrimination || regexp.test(item.data[seriesIndex]))
                &&
                (!showControllersOnly || !info.supportsControllersDiscrimination || item.isController)){
            if(item.data.length > 0) {
                var newRow = tBody.insertRow(-1);
                for(var col=0; col < item.data.length; col++){
                    var cell = newRow.insertCell(-1);
                    cell.innerHTML = formatter ? formatter(col, item.data[col]) : item.data[col];
                }
            }
        }
    }

    // Add support of columns sort
    table.tablesorter({sortList : defaultSorts});
}

$(document).ready(function() {

    // Customize table sorter default options
    $.extend( $.tablesorter.defaults, {
        theme: 'blue',
        cssInfoBlock: "tablesorter-no-sort",
        widthFixed: true,
        widgets: ['zebra']
    });

    var data = {"OkPercent": 0.0, "KoPercent": 100.0};
    var dataset = [
        {
            "label" : "FAIL",
            "data" : data.KoPercent,
            "color" : "#FF6347"
        },
        {
            "label" : "PASS",
            "data" : data.OkPercent,
            "color" : "#9ACD32"
        }];
    $.plot($("#flot-requests-summary"), dataset, {
        series : {
            pie : {
                show : true,
                radius : 1,
                label : {
                    show : true,
                    radius : 3 / 4,
                    formatter : function(label, series) {
                        return '<div style="font-size:8pt;text-align:center;padding:2px;color:white;">'
                            + label
                            + '<br/>'
                            + Math.round10(series.percent, -2)
                            + '%</div>';
                    },
                    background : {
                        opacity : 0.5,
                        color : '#000'
                    }
                }
            }
        },
        legend : {
            show : true
        }
    });

    // Creates APDEX table
    createTable($("#apdexTable"), {"supportsControllersDiscrimination": true, "overall": {"data": [0.0, 500, 1500, "Total"], "isController": false}, "titles": ["Apdex", "T (Toleration threshold)", "F (Frustration threshold)", "Label"], "items": [{"data": [0.0, 500, 1500, "创建会话"], "isController": false}, {"data": [0.0, 500, 1500, "清理缓存(dry_run)"], "isController": false}, {"data": [0.0, 500, 1500, "删除会话"], "isController": false}, {"data": [0.0, 500, 1500, "通知全部已读"], "isController": false}, {"data": [0.0, 500, 1500, "提交评估反馈"], "isController": false}, {"data": [0.0, 500, 1500, "配置预览"], "isController": false}, {"data": [0.0, 500, 1500, "偏好UPSERT"], "isController": false}]}, function(index, item){
        switch(index){
            case 0:
                item = item.toFixed(3);
                break;
            case 1:
            case 2:
                item = formatDuration(item);
                break;
        }
        return item;
    }, [[0, 0]], 3);

    // Create statistics table
    createTable($("#statisticsTable"), {"supportsControllersDiscrimination": true, "overall": {"data": ["Total", 17668, 17668, 100.0, 130.30065655422183, 4, 653, 124.0, 183.0, 244.0, 392.0, 147.38932036405194, 35.0342866121854, 41.306704543558595], "isController": false}, "titles": ["Label", "#Samples", "FAIL", "Error %", "Average", "Min", "Max", "Median", "90th pct", "95th pct", "99th pct", "Transactions/s", "Received", "Sent"], "items": [{"data": ["创建会话", 2529, 2529, 100.0, 137.3345195729539, 5, 638, 127.0, 186.0, 261.0, 401.7999999999993, 21.117587134053675, 5.547491151426209, 5.712472300911004], "isController": false}, {"data": ["清理缓存(dry_run)", 2522, 2522, 100.0, 158.23314829500413, 4, 653, 147.0, 221.70000000000027, 302.0, 428.0, 21.060191061527156, 5.532413472217583, 5.717512807719287], "isController": false}, {"data": ["删除会话", 2526, 2526, 100.0, 120.75494853523348, 8, 496, 113.0, 160.0, 194.0, 380.73, 21.09236049065206, 5.005128463727152, 6.426578586995549], "isController": false}, {"data": ["通知全部已读", 2530, 2530, 100.0, 139.44901185770743, 5, 540, 130.0, 191.0, 250.0, 400.3800000000001, 21.12240979144751, 3.960451835896408, 5.83754098728481], "isController": false}, {"data": ["提交评估反馈", 2513, 2513, 100.0, 139.7994428969361, 8, 543, 129.0, 192.0, 262.2999999999997, 418.72000000000025, 20.989417591687758, 4.796409879350522, 6.415710650584246], "isController": false}, {"data": ["配置预览", 2517, 2517, 100.0, 136.04489471593163, 5, 540, 126.0, 184.0, 247.19999999999982, 399.6400000000003, 21.02089562210827, 5.5220907444796135, 5.645260054765404], "isController": false}, {"data": ["偏好UPSERT", 2531, 2531, 100.0, 80.67759778743576, 5, 471, 74.0, 107.0, 136.0, 285.71999999999935, 21.122117719712584, 4.702971523529755, 5.589935451212999], "isController": false}]}, function(index, item){
        switch(index){
            // Errors pct
            case 3:
                item = item.toFixed(2) + '%';
                break;
            // Mean
            case 4:
            // Mean
            case 7:
            // Median
            case 8:
            // Percentile 1
            case 9:
            // Percentile 2
            case 10:
            // Percentile 3
            case 11:
            // Throughput
            case 12:
            // Kbytes/s
            case 13:
            // Sent Kbytes/s
                item = item.toFixed(2);
                break;
        }
        return item;
    }, [[0, 0]], 0, summaryTableHeader);

    // Create error table
    createTable($("#errorsTable"), {"supportsControllersDiscrimination": false, "titles": ["Type of error", "Number of errors", "% in errors", "% in all samples"], "items": [{"data": ["Test failed: code expected to equal /\\n\\n****** received  : [[[200          ]]]\\n\\n****** comparison: [[[^(?:200|404)$]]]\\n\\n/", 2531, 14.325333937061353, 14.325333937061353], "isController": false}, {"data": ["405/Method Not Allowed", 2531, 14.325333937061353, 14.325333937061353], "isController": false}, {"data": ["422/Unprocessable Entity", 7568, 42.8345030563731, 42.8345030563731], "isController": false}, {"data": ["404/Not Found", 5038, 28.514829069504188, 28.514829069504188], "isController": false}]}, function(index, item){
        switch(index){
            case 2:
            case 3:
                item = item.toFixed(2) + '%';
                break;
        }
        return item;
    }, [[1, 1]]);

        // Create top5 errors by sampler
    createTable($("#top5ErrorsBySamplerTable"), {"supportsControllersDiscrimination": false, "overall": {"data": ["Total", 17668, 17668, "422/Unprocessable Entity", 7568, "404/Not Found", 5038, "Test failed: code expected to equal /\\n\\n****** received  : [[[200          ]]]\\n\\n****** comparison: [[[^(?:200|404)$]]]\\n\\n/", 2531, "405/Method Not Allowed", 2531, "", ""], "isController": false}, "titles": ["Sample", "#Samples", "#Errors", "Error", "#Errors", "Error", "#Errors", "Error", "#Errors", "Error", "#Errors", "Error", "#Errors"], "items": [{"data": ["创建会话", 2529, 2529, "422/Unprocessable Entity", 2529, "", "", "", "", "", "", "", ""], "isController": false}, {"data": ["清理缓存(dry_run)", 2522, 2522, "422/Unprocessable Entity", 2522, "", "", "", "", "", "", "", ""], "isController": false}, {"data": ["删除会话", 2526, 2526, "404/Not Found", 2525, "Test failed: code expected to equal /\\n\\n****** received  : [[[200          ]]]\\n\\n****** comparison: [[[^(?:200|404)$]]]\\n\\n/", 1, "", "", "", "", "", ""], "isController": false}, {"data": ["通知全部已读", 2530, 2530, "Test failed: code expected to equal /\\n\\n****** received  : [[[200          ]]]\\n\\n****** comparison: [[[^(?:200|404)$]]]\\n\\n/", 2530, "", "", "", "", "", "", "", ""], "isController": false}, {"data": ["提交评估反馈", 2513, 2513, "404/Not Found", 2513, "", "", "", "", "", "", "", ""], "isController": false}, {"data": ["配置预览", 2517, 2517, "422/Unprocessable Entity", 2517, "", "", "", "", "", "", "", ""], "isController": false}, {"data": ["偏好UPSERT", 2531, 2531, "405/Method Not Allowed", 2531, "", "", "", "", "", "", "", ""], "isController": false}]}, function(index, item){
        return item;
    }, [[0, 0]], 0);

});
