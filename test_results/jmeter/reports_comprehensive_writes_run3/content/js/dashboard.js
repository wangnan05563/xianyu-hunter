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
    createTable($("#statisticsTable"), {"supportsControllersDiscrimination": true, "overall": {"data": ["Total", 14519, 14519, 100.0, 158.56160892623552, 6, 819, 149.0, 199.0, 244.0, 590.0, 121.21692812476519, 28.811761257378294, 33.9705504813111], "isController": false}, "titles": ["Label", "#Samples", "FAIL", "Error %", "Average", "Min", "Max", "Median", "90th pct", "95th pct", "99th pct", "Transactions/s", "Received", "Sent"], "items": [{"data": ["创建会话", 2077, 2077, 100.0, 165.0722195474242, 7, 797, 152.0, 195.0, 237.19999999999982, 584.5399999999986, 17.3673824336076, 4.562329955703559, 4.698012630966118], "isController": false}, {"data": ["清理缓存(dry_run)", 2072, 2072, 100.0, 192.22731660231668, 7, 819, 176.0, 225.70000000000005, 337.1999999999989, 648.6199999999999, 17.330210772833723, 4.552565134660422, 4.704881440281031], "isController": false}, {"data": ["删除会话", 2073, 2073, 100.0, 151.65846599131714, 10, 749, 135.0, 180.0, 244.5999999999999, 591.2999999999988, 17.339589972648113, 4.1145781055264194, 5.283156319791223], "isController": false}, {"data": ["通知全部已读", 2081, 2081, 100.0, 170.1066794810186, 9, 803, 154.0, 201.0, 265.0, 620.5399999999995, 17.394865965076523, 3.2615373684518487, 4.807370183707673], "isController": false}, {"data": ["提交评估反馈", 2064, 2064, 100.0, 169.58091085271315, 12, 792, 154.0, 202.5, 258.5, 609.0999999999995, 17.26618705035971, 3.9455935251798557, 5.277652877697841], "isController": false}, {"data": ["配置预览", 2069, 2069, 100.0, 165.0270662155635, 6, 775, 152.0, 195.0, 237.0, 581.3000000000002, 17.306566290255123, 4.546353839920536, 4.647759501777499], "isController": false}, {"data": ["偏好UPSERT", 2083, 2083, 100.0, 96.57705232837247, 8, 651, 88.0, 116.0, 137.0, 473.0, 17.393555282780962, 3.872783793431699, 4.603177228157853], "isController": false}]}, function(index, item){
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
    createTable($("#errorsTable"), {"supportsControllersDiscrimination": false, "titles": ["Type of error", "Number of errors", "% in errors", "% in all samples"], "items": [{"data": ["Test failed: code expected to equal /\\n\\n****** received  : [[[200          ]]]\\n\\n****** comparison: [[[^(?:200|404)$]]]\\n\\n/", 2082, 14.339830566843446, 14.339830566843446], "isController": false}, {"data": ["405/Method Not Allowed", 2083, 14.346718093532612, 14.346718093532612], "isController": false}, {"data": ["422/Unprocessable Entity", 6218, 42.82664095323369, 42.82664095323369], "isController": false}, {"data": ["404/Not Found", 4136, 28.486810386390246, 28.486810386390246], "isController": false}]}, function(index, item){
        switch(index){
            case 2:
            case 3:
                item = item.toFixed(2) + '%';
                break;
        }
        return item;
    }, [[1, 1]]);

        // Create top5 errors by sampler
    createTable($("#top5ErrorsBySamplerTable"), {"supportsControllersDiscrimination": false, "overall": {"data": ["Total", 14519, 14519, "422/Unprocessable Entity", 6218, "404/Not Found", 4136, "405/Method Not Allowed", 2083, "Test failed: code expected to equal /\\n\\n****** received  : [[[200          ]]]\\n\\n****** comparison: [[[^(?:200|404)$]]]\\n\\n/", 2082, "", ""], "isController": false}, "titles": ["Sample", "#Samples", "#Errors", "Error", "#Errors", "Error", "#Errors", "Error", "#Errors", "Error", "#Errors", "Error", "#Errors"], "items": [{"data": ["创建会话", 2077, 2077, "422/Unprocessable Entity", 2077, "", "", "", "", "", "", "", ""], "isController": false}, {"data": ["清理缓存(dry_run)", 2072, 2072, "422/Unprocessable Entity", 2072, "", "", "", "", "", "", "", ""], "isController": false}, {"data": ["删除会话", 2073, 2073, "404/Not Found", 2072, "Test failed: code expected to equal /\\n\\n****** received  : [[[200          ]]]\\n\\n****** comparison: [[[^(?:200|404)$]]]\\n\\n/", 1, "", "", "", "", "", ""], "isController": false}, {"data": ["通知全部已读", 2081, 2081, "Test failed: code expected to equal /\\n\\n****** received  : [[[200          ]]]\\n\\n****** comparison: [[[^(?:200|404)$]]]\\n\\n/", 2081, "", "", "", "", "", "", "", ""], "isController": false}, {"data": ["提交评估反馈", 2064, 2064, "404/Not Found", 2064, "", "", "", "", "", "", "", ""], "isController": false}, {"data": ["配置预览", 2069, 2069, "422/Unprocessable Entity", 2069, "", "", "", "", "", "", "", ""], "isController": false}, {"data": ["偏好UPSERT", 2083, 2083, "405/Method Not Allowed", 2083, "", "", "", "", "", "", "", ""], "isController": false}]}, function(index, item){
        return item;
    }, [[0, 0]], 0);

});
